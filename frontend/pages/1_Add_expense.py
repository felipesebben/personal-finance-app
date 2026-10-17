import streamlit as st
import requests
import datetime
from decimal import Decimal
import pandas as pd

from common import (
    SAO_PAULO, auth_headers as headers_for, check, get_data, keep_alive, md, my_user_id as find_my_user_id,
    require_login, show_toast,
)
from config import API_BASE_URL
import entry_checks
from money import entry_preview, format_brl, parse_brl
import ui

INSTALLMENT_PICKS = [1, 2, 3, 6, 10, 12, "Other"]
NATURES = ["Normal", "Extraordinary", "Recurring", "Annual"]

ui.setup("Add expense")
token = require_login()
auth_headers = headers_for(token)
show_toast()


# How a payment method stored without an institution is shown and matched.
NO_INSTITUTION = "N/A"


def cascading_selectbox(label_primary, label_secondary, df, col_primary, col_secondary, key,
                        blank_label=None, help_text_secondary=""):
    """
    Two selects side by side, the second filtered by the first. `key` must
    change when the form resets (it carries the entry form's nonce).

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

# --- Load Data ---
categories_data = get_data("categories", token)
payment_methods_data = get_data("payment_methods", token)
household_data = get_data("household_settings", token)
pets_data = get_data("pets", token)

categories_df = pd.DataFrame(categories_data)

# A pet-category expense with no pet_id was for all the pets.
ALL_PETS = "Both"


def is_pet_category(primary: str, sub: str) -> bool:
    if categories_df.empty or "for_pets" not in categories_df:
        return False
    match = categories_df[(categories_df["primary_category"] == primary) & (categories_df["sub_category"] == sub)]
    return bool(not match.empty and match["for_pets"].eq(True).iloc[0])  # NaN (field missing) would be truthy
payment_methods_df = pd.DataFrame(payment_methods_data)


def is_joint_method(method: str | None, institution: str | None) -> bool:
    """Paid from an account you both fund in advance, so nobody owes for it."""
    if not method or payment_methods_df.empty or "is_joint" not in payment_methods_df:
        return False
    bank = payment_methods_df["institution"].fillna("").replace("", NO_INSTITUTION)
    match = payment_methods_df[(payment_methods_df["method_name"] == method) & (bank == institution)]
    return bool(not match.empty and match["is_joint"].eq(True).iloc[0])

# Who is logged in, for "your share" in the preview.
my_user_id = find_my_user_id(household_data)


@st.fragment
def expense_entry_form():
    """
    The entry form. A fragment, so typing in it reruns only this function
    rather than refetching the overview below, while the cascading selects,
    the credit-only installments and the price preview stay live (st.form
    would freeze them until submit).

    Every widget key carries `entry_nonce`; bumping it after a save gives
    fresh, empty widgets.
    """
    nonce = st.session_state.setdefault("entry_nonce", 0)
    # Typing reruns only this fragment, so renew the session here too.
    keep_alive()

    def k(name):
        return f"entry_{name}_{nonce}"

    # A fresh form starts at now, in São Paulo (the container clock is UTC).
    if k("date") not in st.session_state:
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
                pick = st.segmented_control(
                    "💳 Installments", INSTALLMENT_PICKS, default=1, key=k("inst_pick"),
                    format_func=lambda p: p if p == "Other" else f"{p}x",
                    help="1x = paid in full. Enter an installment purchase **once**, with its full price; "
                         "Tableau's cashflow datasource spreads it over the months.",
                )
                if pick == "Other":
                    total_inst = int(st.number_input("Number of installments", min_value=2, value=2, step=1, key=k("inst_other")))
                else:
                    total_inst = pick or 1
            if total_inst > 1:
                current_inst = int(inst_b.number_input(
                    "Installment billed this month", min_value=1, max_value=total_inst, value=1,
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
    if selected_sub and is_pet_category(selected_primary, selected_sub):
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
    if is_joint_method(selected_method_name, selected_institution):
        is_shared = st.toggle("Shared Household Expense?", value=True, disabled=True, key=k("shared_joint"))
        st.caption("Paid from the joint account, so nobody owes anything for this. "
                   "It still counts towards each person's share of spending.")
    else:
        is_shared = st.toggle("Shared Household Expense?", value=True, key=k("shared"),
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
            share_cols = st.columns(len(household_data))
            custom_shares = []
            for share_col, member in zip(share_cols, household_data):
                name = member["user"].get("full_name") or member["user"]["email"]
                pct = share_col.number_input(
                    f"{name} %", min_value=0, max_value=100, step=5,
                    value=int(round(float(member["share_pct"]) * 100)), key=k(f"share_{member['user_id']}"),
                )
                custom_shares.append((member["user_id"], pct))
            split_total = sum(pct for _, pct in custom_shares)
            if split_total != 100:
                st.warning(f"Shares add up to {split_total}%, not 100%.")

    # 6. Nature, then when.
    nature_option = st.segmented_control(
        "Nature", NATURES, default="Normal", key=k("nature"),
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
        else:
            preview_shares = [(m["user_id"], Decimal(str(m["share_pct"]))) for m in household_data or []]
        price_slot.caption(md(entry_preview(price, total_inst, preview_shares, my_user_id)))

    def send(payload: dict) -> None:
        """POST it; on success reset the form, on a likely duplicate ask first."""
        try:
            response = check(requests.post(f"{API_BASE_URL}/expenditures/", json=payload,
                                           headers=headers_for(st.session_state["access_token"])))
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
        # Fresh widgets next time, a toast after the rerun, and the overview
        # below refetched with the new expense in it.
        st.session_state.pop(k("duplicate"), None)
        st.session_state["entry_nonce"] = nonce + 1
        st.session_state["tracker_toast"] = f"Expense saved: {format_brl(Decimal(payload['price']))}"
        st.cache_data.clear()
        st.rerun(scope="app")

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
    if not st.button("Submit Expenditure", type="primary", key=k("submit")):
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
            "user_id": 0, # Backend handles this via token
            "current_installment": current_inst,
            "total_installments": total_inst
        }
        if pet_id is not None:
            payload["pet_id"] = int(pet_id)
        if custom_shares is not None:
            # People at 0% simply bear none of it, so they get no row.
            payload["shares"] = [
                {"user_id": uid, "share_pct": f"{pct / 100:.2f}"} for uid, pct in custom_shares if pct > 0
            ]
    except Exception as e:
        st.error(f"Error processing request: {e}")
        return

    send(payload)


# -- Main Page UI --
ui.page_header("Add expense", "Record one purchase. See how it's going on Our expenses and My expenses.")


def ratio_text() -> str:
    """'Felipe 60% · Lívia 40%', from the household split, or '' if none is set."""
    parts = [
        f"{m['user'].get('full_name') or m['user']['email']} {Decimal(str(m['share_pct'])) * 100:.0f}%"
        for m in household_data or []
    ]
    return " · ".join(parts)


ratio = ratio_text()
ui.lede(
    "Record one purchase.",
    (f" Shared expenses are split between you by the household ratio ({ratio}); " if ratio
     else " Shared expenses are split between you by the household ratio; ")
    + "personal ones stay private to you.",
)
# Where logging has got to, to see where backfilling stopped.
for line in entry_checks.backfill_lines(get_data("expenditures", token), my_user_id, SAO_PAULO):
    st.caption(md(line))
if categories_df.empty or payment_methods_df.empty:
    st.warning("Add at least one category and one payment method on the **Settings** page first.")
    st.page_link("pages/5_Settings.py", label="Open Settings", icon=":material/settings:")
else:
    if not household_data:
        st.info("No household split is set yet, so shared expenses can't be saved. Set it on the Settings page.")
    with st.expander("What does “shared” change?"):
        st.write(
            "A **shared** expense is visible to both of you, and each of you bears your share of it "
            "by the household ratio (or by a custom split you set for that one expense). "
            "Turn **Shared** off for something only you pay for: your partner won't see it."
        )
    expense_entry_form()
