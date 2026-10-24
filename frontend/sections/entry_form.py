"""
The expense form, shared by Add expense (a new expense, POST) and Entries
(an existing one, PATCH, its fields filled in). One form, so an edit
follows exactly the rules of an entry: cascading selects, credit-only
installments, the joint-account lock, "it's on me", a pet for a pet
category, a custom split and the live price preview.

Not a fragment itself: Add expense wraps it in @st.fragment so typing
reruns only the form. Every widget key is `<prefix>_<name>_<nonce>`; bump
the nonce in session state (`<prefix>_nonce`) to get fresh widgets.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd
import requests
import streamlit as st

import entry_checks
from common import SAO_PAULO, auth_headers, check, get_data, keep_alive, md, my_user_id as find_my_user_id
from config import API_BASE_URL
from entries import NO_INSTITUTION, form_values
from money import entry_preview, format_brl, parse_brl
from shares import fill_rest_in_state

INSTALLMENT_PICKS = [1, 2, 3, 6, 10, 12, "Other"]
NATURES = ["Normal", "Extraordinary", "Recurring", "Annual"]
# A pet-category expense with no pet_id was for all the pets.
ALL_PETS = "Both"


def cascading_selectbox(label_primary, label_secondary, df, col_primary, col_secondary, key,
                        blank_label=None, help_text_secondary=""):
    """
    Two selects side by side, the second filtered by the first. `key` must
    change when the form resets (it carries the form's nonce).

    With `blank_label` set, rows whose secondary value is empty are offered
    as that label (e.g. a payment method stored without an institution). When
    it is the only option it is picked and locked, so the form never asks for
    a value the data doesn't have.
    """
    col_a, col_b = st.columns(2)
    primary_options = sorted(df[col_primary].unique()) if not df.empty else []
    selected_primary = col_a.selectbox(
        label_primary, options=primary_options, index=None,
        placeholder=f"Select {label_primary}...", key=f"{key}_primary",
    )

    secondary_options = []
    disabled_secondary = True
    index_secondary = None
    dynamic_help = ""

    if selected_primary:
        values = df.loc[df[col_primary] == selected_primary, col_secondary]
        named = sorted({x for x in values.dropna() if x})
        has_blank = blank_label is not None and (values.isna() | (values == "")).any()
        secondary_options = named + ([blank_label] if has_blank else [])
        if named:
            disabled_secondary = False
            dynamic_help = help_text_secondary
        elif has_blank:
            index_secondary = 0
            dynamic_help = f"No {label_secondary.lower()} is registered for **{selected_primary}**."

    # The primary choice is part of the key, so switching it starts the
    # secondary select afresh instead of keeping a value it no longer offers.
    selected_secondary = col_b.selectbox(
        label_secondary, options=secondary_options, index=index_secondary,
        placeholder=f"Select {label_secondary}...", disabled=disabled_secondary, help=dynamic_help,
        key=f"{key}_secondary_{selected_primary}",
    )
    return selected_primary, selected_secondary


class Lookups:
    """What the form picks from: categories, payment methods, the household and the pets."""

    def __init__(self, token: str):
        self.categories = pd.DataFrame(get_data("categories", token))
        self.payment_methods = pd.DataFrame(get_data("payment_methods", token))
        self.household = get_data("household_settings", token)
        self.pets = get_data("pets", token)
        self.my_user_id = find_my_user_id(self.household)

    @property
    def ready(self) -> bool:
        return not self.categories.empty and not self.payment_methods.empty

    def is_pet_category(self, primary: str, sub: str) -> bool:
        df = self.categories
        if df.empty or "for_pets" not in df:
            return False
        match = df[(df["primary_category"] == primary) & (df["sub_category"] == sub)]
        return bool(not match.empty and match["for_pets"].eq(True).iloc[0])  # NaN (field missing) would be truthy

    def is_joint_method(self, method: str | None, institution: str | None) -> bool:
        """Paid from an account you both fund in advance, so nobody owes for it."""
        df = self.payment_methods
        if not method or df.empty or "is_joint" not in df:
            return False
        bank = df["institution"].fillna("").replace("", NO_INSTITUTION)
        match = df[(df["method_name"] == method) & (bank == institution)]
        return bool(not match.empty and match["is_joint"].eq(True).iloc[0])


def _prefill(k, values: dict) -> None:
    """
    Put an existing expense's values into the widgets' state, once (until
    the nonce changes). Only for widgets without a default of their own:
    Streamlit warns when a widget gets both, so the toggle, the number
    inputs and the segmented controls take theirs from `value=`/`default=`.
    """
    if k("price") in st.session_state:
        return
    st.session_state[k("price")] = values["price_text"]
    # The cascading selects' own keys: <key>_primary and <key>_secondary_<primary>.
    st.session_state[f"{k('payment')}_primary"] = values["method"]
    st.session_state[f"{k('payment')}_secondary_{values['method']}"] = values["institution"]
    st.session_state[f"{k('category')}_primary"] = values["primary"]
    st.session_state[f"{k('category')}_secondary_{values['primary']}"] = values["sub"]
    if values["pet"] is not None:
        st.session_state[k("pet")] = values["pet"]
    st.session_state[k("treat")] = values["treat"]
    st.session_state[k("custom")] = values["custom"] is not None
    st.session_state[k("date")] = values["date"]
    st.session_state[k("time")] = values["time"]


def render(token: str, data: Lookups, prefix: str = "entry", expense: dict | None = None,
           submit_label: str = "Submit Expenditure", on_saved=None,
           templates: list[tuple[str, dict]] | None = None) -> None:
    """
    The form. Without `expense` it adds one (POST, asking first about a
    likely duplicate); with an `expense` from GET /expenditures/ it edits
    that one (PATCH, only what the form holds, keeping the split it was
    logged with unless you change it).

    `templates` (entries.recent_templates) adds a "Log again" row: picking
    one fills the form in from that expense, dated now and with no price,
    and it's saved as a new expense (POST).

    On success: `on_saved()` if given, a toast, the cache cleared, fresh
    widgets (nonce bumped) and a rerun of the whole page.
    """
    nonce_key = f"{prefix}_nonce"
    nonce = st.session_state.setdefault(nonce_key, 0)
    # Typing reruns only this form (a fragment on Add expense), so renew the session here too.
    keep_alive()
    categories_df, payment_methods_df = data.categories, data.payment_methods
    household_data, pets_data, my_user_id = data.household, data.pets, data.my_user_id

    def k(name):
        return f"{prefix}_{name}_{nonce}"

    names = {m["user_id"]: m["user"].get("full_name") or m["user"]["email"] for m in household_data or []}
    # "Log again": the picked recent expense, kept apart from its pills (whose key carries the nonce).
    template_key = f"{prefix}_template"
    if templates and expense is None:
        by_label = dict(templates)

        def pick() -> None:
            st.session_state[template_key] = st.session_state.get(k("repeat"))
            st.session_state[nonce_key] = nonce + 1  # fresh widgets, filled in from it

        st.pills("Log again", list(by_label), key=k("repeat"), on_change=pick,
                 help="Your recent expenses: pick one to fill the form in, then type the price.")
    picked = (dict(templates or []).get(st.session_state.get(template_key)) if expense is None else None)

    # The values the form starts from: the expense being edited, or the one picked to log again.
    original = form_values(expense, data.pets, SAO_PAULO, names) if expense else None
    start = original
    if picked:
        start = form_values(picked, data.pets, SAO_PAULO, names)
        now = datetime.datetime.now(SAO_PAULO)
        start.update(price_text="", date=now.date(), time=now.time().replace(second=0, microsecond=0))
        st.caption(f"Filled in from {st.session_state[template_key]}. Type the price.")
    if start:
        _prefill(k, start)
    # A fresh form starts at now, in São Paulo (the container clock is UTC).
    elif k("date") not in st.session_state:
        now = datetime.datetime.now(SAO_PAULO)
        st.session_state[k("date")] = now.date()
        st.session_state[k("time")] = now.time().replace(second=0, microsecond=0)

    # 1. Price, read back underneath once the rest of the form is known.
    price_col, _ = st.columns(2)
    with price_col:
        price_text = st.text_input(
            "Price (R$)", placeholder="0,00", key=k("price"),
            help="Type it the Brazilian way, e.g. 1.234,56. For an installment purchase, the **full** price, not one installment.",
        )
        price_slot = st.empty()

    price, price_error = None, None
    if price_text.strip():
        try:
            price = parse_brl(price_text)
        except ValueError as e:
            price_error = str(e)

    # 2. How it was paid.
    selected_method_name, selected_institution = cascading_selectbox(
        label_primary="Payment Method", label_secondary="Institution",
        df=payment_methods_df, col_primary="method_name", col_secondary="institution",
        key=k("payment"), blank_label=NO_INSTITUTION,
    )
    if selected_institution == NO_INSTITUTION and selected_method_name != "Cash":
        st.caption(
            f"Want to record which account paid? Add e.g. *{selected_method_name} · Nubank* "
            "in Settings → Payment methods."
        )

    # 3. Installments, for credit only.
    current_inst = 1
    total_inst = 1
    if selected_method_name:
        matched_pm = payment_methods_df[payment_methods_df["method_name"] == selected_method_name]
        is_credit = bool(matched_pm["is_credit"].iloc[0]) if not matched_pm.empty and "is_credit" in payment_methods_df.columns else False
        if is_credit:
            inst_a, inst_b = st.columns(2)
            with inst_a:
                start_total = start["total_installments"] if start else 1
                pick = st.segmented_control(
                    "💳 Installments", INSTALLMENT_PICKS, key=k("inst_pick"),
                    default=start_total if start_total in INSTALLMENT_PICKS else "Other",
                    format_func=lambda p: p if p == "Other" else f"{p}x",
                    help="1x = paid in full. Enter an installment purchase **once**, with its full price; "
                         "Tableau's cashflow datasource spreads it over the months.",
                )
                if pick == "Other":
                    other = start_total if start_total not in INSTALLMENT_PICKS else 2
                    total_inst = int(st.number_input("Number of installments", min_value=2, value=other, step=1,
                                                     key=k("inst_other")))
                else:
                    total_inst = pick or 1
            if total_inst > 1:
                billed = start["current_installment"] if start and total_inst == start_total else 1
                current_inst = int(inst_b.number_input(
                    "Installment billed this month", min_value=1, max_value=total_inst, value=min(billed, total_inst),
                    key=k(f"inst_current_{total_inst}"),
                    help="1 if you're entering it on the day you bought it; e.g. 4 if you're already paying installment 4 of 10.",
                ))

    # 4. What it was.
    selected_primary, selected_sub = cascading_selectbox(
        label_primary="Category", label_secondary="Sub-Category",
        df=categories_df, col_primary="primary_category", col_secondary="sub_category",
        key=k("category"),
    )

    # 4b. For a pet category, which pet. "Both" is sent as no pet_id.
    pet_id, pet_choice_missing = None, False
    if selected_sub and data.is_pet_category(selected_primary, selected_sub):
        if not pets_data:
            st.caption("Want to know what each pet costs? Add them in Settings → Pets.")
        elif len(pets_data) == 1:
            pet_id = pets_data[0]["pet_id"]
            st.caption(f"For {pets_data[0]['name']}.")
        else:
            names = {p["name"]: p["pet_id"] for p in sorted(pets_data, key=lambda p: p["name"].lower())}
            choice = st.radio("Which pet?", [*names, ALL_PETS], index=None, horizontal=True, key=k("pet"),
                              help=f"{ALL_PETS}: one expense for all of them, e.g. a bag of food they share.")
            pet_id = names.get(choice)
            pet_choice_missing = choice is None

    # 5. Who bears it. The joint account only pays for shared things, and
    # since you both fund it, nobody owes the other for what it paid.
    is_treat = False
    if data.is_joint_method(selected_method_name, selected_institution):
        is_shared = st.toggle("Shared Household Expense?", value=True, disabled=True, key=k("shared_joint"))
        st.caption("Paid from the joint account, so nobody owes anything for this. "
                   "It still counts towards each person's share of spending.")
    else:
        is_shared = st.toggle("Shared Household Expense?", value=start["shared"] if start else True,
                              key=k("shared"),
                              help="Leave ON if split between couple.")
        # "It's on me": still shared and split (it counts in both shares),
        # but nobody owes you for it.
        if is_shared:
            others = [m["user"].get("full_name") or m["user"]["email"]
                      for m in household_data or [] if m["user_id"] != my_user_id]
            who = " and ".join(others) or "Your partner"
            is_treat = st.checkbox(
                f"It's on me: {who} doesn't pay their share back",
                key=k("treat"),
                help="Still a shared expense, split as usual, so it counts in both your shares. "
                     "It just never shows up in Settle up.",
            )

    # Optional per-expense override of the household ratio, sent as "shares".
    custom_shares = None
    if is_shared and household_data:
        if st.checkbox("Custom split for this expense", key=k("custom"),
                       help="Override the household ratio just for this one, e.g. 70/30, or 100% on one person."):
            members = sorted(household_data, key=lambda m: m["user_id"] != my_user_id)  # you first, as in Settings
            share_cols = st.columns(len(members))
            custom_shares = []
            share_keys = {m["user_id"]: k(f"share_{m['user_id']}") for m in members}
            for share_col, member in zip(share_cols, members):
                name = member["user"].get("full_name") or member["user"]["email"]
                start_pct = int(round(float(member["share_pct"]) * 100))
                if start and start["custom"] is not None:
                    start_pct = start["custom"].get(member["user_id"], 0)
                key = share_keys[member["user_id"]]
                # Seeded here, not passed as value=: the other input's callback writes to it.
                st.session_state.setdefault(key, start_pct)
                pct = share_col.number_input(
                    f"{name} %", min_value=0, max_value=100, step=5, key=key,
                    on_change=fill_rest_in_state, args=(st.session_state, share_keys, member["user_id"]),
                    help="With two people, the other share becomes the rest." if len(household_data) == 2 else None,
                )
                custom_shares.append((member["user_id"], pct))
            split_total = sum(pct for _, pct in custom_shares)
            if split_total != 100:
                st.warning(f"Shares add up to {split_total}%, not 100%.")
        elif original and original["was_shared"] and original["custom"] is None:
            st.caption("Split as when it was logged: " + original["split_text"] + ".")

    # 6. Nature, then when.
    nature_option = st.segmented_control(
        "Nature", NATURES, default=start["nature"] if start else "Normal", key=k("nature"),
        help="Normal: everyday | Extraordinary: unplanned/emergency | Recurring: monthly subscription | Annual: once-a-year (IPVA, IPTU)",
    )
    date_col, time_col = st.columns(2)
    date_input = date_col.date_input("Date", format="DD/MM/YYYY", key=k("date"))
    time_input = time_col.time_input("Time", step=60, key=k("time"))

    # The preview, under the price field.
    if price_error:
        price_slot.error(price_error)
    elif price is not None:
        if not is_shared:
            preview_shares = None
        elif custom_shares is not None:
            preview_shares = [(uid, Decimal(pct) / 100) for uid, pct in custom_shares]
        elif original and original["was_shared"]:
            preview_shares = original["split"]  # an edit keeps the split it was logged with
        else:
            preview_shares = [(m["user_id"], Decimal(str(m["share_pct"]))) for m in household_data or []]
        price_slot.caption(md(entry_preview(price, total_inst, preview_shares, my_user_id)))

    def done(message: str) -> None:
        """Fresh widgets next time, a toast after the rerun, and every view refetched."""
        if on_saved is not None:
            on_saved()
        st.session_state.pop(template_key, None)  # the next one starts empty
        st.session_state.pop(k("duplicate"), None)
        st.session_state[nonce_key] = nonce + 1
        st.session_state["tracker_toast"] = message
        st.cache_data.clear()
        st.rerun(scope="app")

    def send(payload: dict) -> None:
        """POST it; on success reset the form, on a likely duplicate ask first."""
        try:
            response = check(requests.post(f"{API_BASE_URL}/expenditures/", json=payload,
                                           headers=auth_headers(st.session_state["access_token"])))
        except requests.exceptions.RequestException as e:
            st.error(f"Error processing request: {e}")
            return
        if response.status_code == 409:
            # Already logged (by you, or a shared one by your partner): ask before saving.
            st.session_state[k("duplicate")] = {"payload": payload, "duplicates": response.json()["detail"]["duplicates"]}
            st.rerun()
        if response.status_code != 200:
            st.error(f"Error: {response.status_code} – {response.text}")
            return
        done(f"Expense saved: {format_brl(Decimal(payload['price']))}")

    def update(payload: dict) -> None:
        """PATCH it; the API changes only what differs and leaves a trace of the edit."""
        try:
            response = check(requests.patch(f"{API_BASE_URL}/expenditures/{expense['expenditure_id']}",
                                            json=payload, headers=auth_headers(st.session_state["access_token"])))
        except requests.exceptions.RequestException as e:
            st.error(f"Error processing request: {e}")
            return
        if response.status_code != 200:
            st.error(f"Error: {response.status_code} – {response.text}")
            return
        done(f"Expense updated: {format_brl(Decimal(payload['price']))}")

    # --- A likely duplicate, waiting for a decision ---
    pending = st.session_state.get(k("duplicate"))
    if pending:
        with st.container(border=True):
            st.warning("This looks like an expense that's already logged.", icon=":material/content_copy:")
            for line in entry_checks.duplicate_lines(pending["duplicates"], SAO_PAULO):
                st.markdown(f"- {md(line)}")
            keep, drop = st.columns(2)
            if keep.button("Save anyway", key=k("save_anyway"), width="stretch"):
                send({**pending["payload"], "allow_duplicate": True})
            if drop.button("Don't save", key=k("drop_duplicate"), type="primary", width="stretch"):
                st.session_state.pop(k("duplicate"), None)
                st.rerun()
        return

    # --- Submit button ---
    if not st.button(submit_label, type="primary", key=k("submit")):
        return

    # 1. Validation
    missing_fields = []
    if price is None: missing_fields.append("Price" if not price_error else f"Price ({price_error})")
    if not selected_method_name: missing_fields.append("Payment Method")
    if not selected_institution: missing_fields.append("Institution")
    if not selected_primary: missing_fields.append("Category")
    if not selected_sub: missing_fields.append("Sub-Category")
    if pet_choice_missing: missing_fields.append("Which pet")
    if not nature_option: missing_fields.append("Nature")
    if custom_shares is not None and sum(pct for _, pct in custom_shares) != 100:
        missing_fields.append("Custom split (must add up to 100%)")

    if missing_fields:
        st.error(f"⚠️ Please fill out: **{', '.join(missing_fields)}**")
        return

    try:
        # 2. Lookups
        matched_method = payment_methods_df[
            (payment_methods_df["method_name"] == selected_method_name) &
            (payment_methods_df["institution"].fillna("").replace("", NO_INSTITUTION) == selected_institution)
        ]
        payment_method_id = matched_method["payment_method_id"].iloc[0]

        category_id = categories_df[
            (categories_df["primary_category"] == selected_primary) &
            (categories_df["sub_category"] == selected_sub)
        ]["category_id"].iloc[0]

        # 3. Payload
        dt_aware = datetime.datetime.combine(date_input, time_input).replace(tzinfo=SAO_PAULO)

        payload = {
            "transaction_timestamp": dt_aware.isoformat(),
            # A string, so the exact Decimal reaches the API's Numeric(10, 2).
            "price": str(price),
            "category_id": int(category_id),
            "payment_method_id": int(payment_method_id),
            "nature": nature_option,
            "is_shared": is_shared,
            "is_treat": bool(is_shared and is_treat),
            "current_installment": current_inst,
            "total_installments": total_inst
        }
        if custom_shares is not None:
            # People at 0% simply bear none of it, so they get no row.
            payload["shares"] = [
                {"user_id": uid, "share_pct": f"{pct / 100:.2f}"} for uid, pct in custom_shares if pct > 0
            ]
    except Exception as e:
        st.error(f"Error processing request: {e}")
        return

    if expense is None:
        payload["user_id"] = 0  # Backend handles this via token
        if pet_id is not None:
            payload["pet_id"] = int(pet_id)
        send(payload)
        return
    # An edit says "all the pets" (or "no pet") explicitly, and drops a custom
    # split that was unticked back to the household ratio.
    payload["pet_id"] = int(pet_id) if pet_id is not None else None
    if is_shared and custom_shares is None and original["custom"] is not None:
        payload["reset_split"] = True
    update(payload)
