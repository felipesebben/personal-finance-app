import streamlit as st
import requests
import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
import pandas as pd

from config import API_BASE_URL
from money import entry_preview, format_brl, format_brl_delta, parse_brl
import ui

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
INSTALLMENT_PICKS = [1, 2, 3, 6, 10, 12, "Other"]
NATURES = ["Normal", "Extraordinary", "Recurring", "Annual"]

# Page Configuration
ui.setup("Tracker")

# --- Authentication check ---
if "access_token" not in st.session_state or st.session_state["access_token"] is None:
    st.error("You are not logged in.")
    st.info("Please go to the **Home** page to log in.")
    st.stop()

auth_headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}

# A save reruns the page straight away, so anything shown before st.rerun()
# is lost; its confirmation is stashed in session_state and shown here instead.
def md(text: str) -> str:
    """Escapes "$" for Markdown elements, where a pair of them starts LaTeX ("R$ 1 · R$ 2")."""
    return text.replace("$", "\\$")


if "tracker_toast" in st.session_state:
    st.toast(md(st.session_state.pop("tracker_toast")), icon="✅")

# --- Helper functions ---
@st.cache_data(ttl=60)
def get_data(endpoint: str, token: str):
    """
    Streamlit re-runs the function if the token changes.

    :param endpoint: API endpoint.
    :type endpoint: str
    :param token: Current token for session.
    :type token: str
    """
    local_headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}", headers=local_headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.error("Session Expired. Please log in again.")
            return []
        else:
            st.error(f"Failed to fetch {endpoint}. Status code: {response.status_code}")
            return []
    except requests.exceptions.ConnectionError:
        st.error(f"Connection Error: Could not connect to the API to fetch {endpoint}.")
        return []


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
token = st.session_state["access_token"]

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

# Who is logged in, for "your share" in the preview: Home.py keeps the login email.
my_email = (st.session_state.get("user_email") or "").strip().lower()
my_user_id = next(
    (m["user_id"] for m in household_data or [] if (m["user"].get("email") or "").lower() == my_email),
    None,
)


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
    if is_joint_method(selected_method_name, selected_institution):
        is_shared = st.toggle("Shared Household Expense?", value=True, disabled=True, key=k("shared_joint"))
        st.caption("Paid from the joint account, so nobody owes anything for this. "
                   "It still counts towards each person's share of spending.")
    else:
        is_shared = st.toggle("Shared Household Expense?", value=True, key=k("shared"),
                              help="Leave ON if split between couple.")

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

        # 4. Request
        response = requests.post(f"{API_BASE_URL}/expenditures/", json=payload, headers=auth_headers)
    except Exception as e:
        st.error(f"Error processing request: {e}")
        return

    if response.status_code != 200:
        st.error(f"Error: {response.status_code} – {response.text}")
        return

    # Fresh widgets next time, a toast after the rerun, and the overview
    # below refetched with the new expense in it.
    st.session_state["entry_nonce"] = nonce + 1
    st.session_state["tracker_toast"] = f"Expense saved: {format_brl(price)}"
    st.cache_data.clear()
    st.rerun(scope="app")


# -- Main Page UI --
ui.page_header("Tracker", "Log what you spend, see where this month stands, and square up with each other.")

today_brl = datetime.datetime.now(SAO_PAULO).date()


def month_options(include_all_time: bool) -> list[str]:
    """The last 12 São Paulo months, newest first, optionally plus "All time"."""
    options, y, m = [], today_brl.year, today_brl.month
    for _ in range(12):
        options.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return options + (["All time"] if include_all_time else [])


def period_label(period: str) -> str:
    return period if period == "All time" else datetime.date(int(period[:4]), int(period[5:]), 1).strftime("%B %Y")


def ratio_text() -> str:
    """'Felipe 60% · Lívia 40%', from the household split, or '' if none is set."""
    parts = [
        f"{m['user'].get('full_name') or m['user']['email']} {Decimal(str(m['share_pct'])) * 100:.0f}%"
        for m in household_data or []
    ]
    return " · ".join(parts)


add_tab, month_tab, settle_tab, history_tab = st.tabs(["Add expense", "This month", "Settle up", "History"])

# --- Add expense -----------------------------------------------------------
with add_tab:
    ratio = ratio_text()
    ui.lede(
        "Record one purchase.",
        (f" Shared expenses are split between you by the household ratio ({ratio}); " if ratio
         else " Shared expenses are split between you by the household ratio; ")
        + "personal ones stay private to you.",
    )
    if categories_df.empty or payment_methods_df.empty:
        st.warning("Add at least one category and one payment method on the **Settings** page first.")
        st.page_link("pages/3_Manage_Settings_.py", label="Open Settings", icon=":material/settings:")
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

# --- This month ------------------------------------------------------------
with month_tab:
    ui.lede(
        "Your spending this month, at a glance.",
        " “You spent” is your part of shared expenses plus your personal ones. "
        "To compare months and see trends, open Analytics.",
    )
    selected_month = st.selectbox(
        "Month", options=month_options(include_all_time=False), index=0,
        format_func=period_label, key="month_tab_period",
    )
    summary = get_data(f"summary/?month={selected_month}", token)
    if summary:
        me, household = summary["me"], summary["household_shared"]
        previous = period_label(summary["previous_month"])

        def change(now, before):
            return f"{format_brl_delta(Decimal(now) - Decimal(before))} vs {previous}"

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("You spent", format_brl(me["total"]), delta=change(me["total"], me["previous_total"]),
                      delta_color="inverse", border=True)
            st.caption("Your share of shared expenses + your personal ones.")
        with m2:
            st.metric("Your share of shared", format_brl(me["shared_share"]), border=True)
            st.caption(f"Plus {md(format_brl(me['personal']))} personal.")
        with m3:
            st.metric("Household shared total", format_brl(household["total"]),
                      delta=change(household["total"], household["previous_total"]),
                      delta_color="inverse", border=True)
            st.caption("Everything you both shared, whoever paid.")
        st.caption("▲ means more than the previous month, ▼ less.")

        if summary["by_category"]:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("Where your money went")
                st.caption("Your part of each category this month, biggest first.")
                cat_df = pd.DataFrame(summary["by_category"]).rename(columns={"label": "Category", "amount": "Amount"})
                cat_df["Amount"] = pd.to_numeric(cat_df["Amount"])
                st.bar_chart(cat_df, x="Category", y="Amount", horizontal=True, sort="-Amount")
            with c2:
                st.subheader("Fixed vs variable")
                st.caption("Fixed costs repeat every month (rent, internet); variable ones change.")
                ct_df = pd.DataFrame(summary["by_cost_type"]).rename(columns={"label": "Cost type", "amount": "Amount"})
                amounts = pd.to_numeric(ct_df["Amount"])
                total = amounts.sum()
                ct_df["Share"] = amounts / total * 100 if total else 0
                # Pre-formatted text: NumberColumn can't put a comma before the cents.
                ct_df["Amount"] = ct_df["Amount"].map(format_brl)
                st.dataframe(
                    ct_df, width="stretch", hide_index=True,
                    column_config={
                        "Share": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
                    },
                )
        else:
            st.info("Nothing logged for this month yet. Add an expense in the **Add expense** tab.")
        st.page_link("pages/2_Analytics.py", label="Compare with earlier months in Analytics", icon=":material/monitoring:")

# --- Settle up -------------------------------------------------------------
with settle_tab:
    ui.lede(
        "Who owes whom, and recording the payment.",
        " Compares what each of you paid for shared expenses with what the household ratio says "
        "you should have paid, minus payments already recorded.",
    )
    selected_period = st.selectbox(
        "Period", options=month_options(include_all_time=True), index=0,
        format_func=period_label, key="settle_tab_period",
        help="Usually the month you're squaring up. “All time” is the running balance across every month.",
    )
    label = period_label(selected_period)
    balance_endpoint = "balances/" if selected_period == "All time" else f"balances/?month={selected_period}"
    balance_report = get_data(balance_endpoint, token)

    if balance_report:
        if balance_report["transfers"]:
            for t in balance_report["transfers"]:
                ui.callout(f"{t['from_name']} owes {t['to_name']}", format_brl(t["amount"]),
                           f"for {label} · after payments already recorded")
        else:
            ui.callout("All square", "", f"Nobody owes anything for {label}.")

        balance_df = pd.DataFrame(balance_report["members"])
        if not balance_df.empty:
            st.subheader("How we got there")
            st.caption(
                "**Paid**: what went out of each person's account for shared expenses. "
                "**Should have paid**: their share by the household ratio. "
                "**Difference**: paid − should have paid + paid back − received; "
                "positive means the others owe this person."
            )
            money_cols = {
                "paid": "Paid", "borne": "Should have paid",
                "settled_out": "Paid back", "settled_in": "Received", "net": "Difference",
            }
            for col in money_cols:
                balance_df[col] = balance_df[col].map(format_brl)
            st.dataframe(
                balance_df[["full_name", *money_cols]].rename(columns={"full_name": "Person", **money_cols}),
                width="stretch", hide_index=True,
            )

        members = {m["user_id"]: m["full_name"] for m in balance_report["members"]}
        suggestion = balance_report["transfers"][0] if balance_report["transfers"] else None
        squares_up = "the running all-time balance" if selected_period == "All time" else label
        month_value = None if selected_period == "All time" else selected_period

        def record_settlement(from_id, to_id, amount, paid_on, note):
            now_brl = datetime.datetime.now(SAO_PAULO)
            payload = {
                "settled_at": datetime.datetime.combine(paid_on, now_brl.time(), tzinfo=SAO_PAULO).isoformat(),
                "from_user_id": from_id,
                "to_user_id": to_id,
                "amount": str(amount),
                "month": month_value,
                "note": note or None,
            }
            res = requests.post(f"{API_BASE_URL}/settlements/", json=payload, headers=auth_headers)
            if res.status_code == 200:
                st.session_state["tracker_toast"] = f"Payment recorded: {format_brl(amount)}"
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")

        if suggestion:
            owed = Decimal(str(suggestion["amount"]))
            with st.popover(f"Record {suggestion['from_name']}'s payment of {format_brl(owed)}", icon=":material/payments:"):
                st.write(
                    f"{suggestion['from_name']} paid {suggestion['to_name']} **{md(format_brl(owed))}**, "
                    f"squaring up {squares_up}."
                )
                quick_date = st.date_input("Paid on", today_brl, format="DD/MM/YYYY", key="quick_paid_on")
                quick_note = st.text_input("Note (optional)", placeholder="e.g. Pix transfer", key="quick_note")
                if st.button("Confirm payment", type="primary", key="quick_confirm"):
                    record_settlement(suggestion["from_user_id"], suggestion["to_user_id"], owed, quick_date, quick_note)

        if len(members) >= 2:
            with st.expander("Record a different payment (partial amount, other direction)"):
                st.caption(f"Squares up **{squares_up}**.")
                member_ids = list(members)
                with st.form("settlement_form", clear_on_submit=True):
                    f1, f2 = st.columns(2)
                    from_id = f1.selectbox(
                        "From", member_ids, format_func=members.get,
                        index=member_ids.index(suggestion["from_user_id"]) if suggestion else 0,
                    )
                    to_id = f2.selectbox(
                        "To", member_ids, format_func=members.get,
                        index=member_ids.index(suggestion["to_user_id"]) if suggestion else 1,
                    )
                    f3, f4 = st.columns(2)
                    amount_text = f3.text_input(
                        "Amount (R$)", placeholder="0,00",
                        value=format_brl(suggestion["amount"], symbol=False) if suggestion else "",
                    )
                    paid_on = f4.date_input("Paid on", today_brl, format="DD/MM/YYYY")
                    note = st.text_input("Note (optional)", placeholder="e.g. Pix transfer")

                    if st.form_submit_button("Record payment", type="primary"):
                        try:
                            amount, amount_error = parse_brl(amount_text), None
                        except ValueError as e:
                            amount, amount_error = None, str(e)
                        if from_id == to_id:
                            st.error("From and To must be different people.")
                        elif amount_error:
                            st.error(f"Amount: {amount_error}")
                        else:
                            record_settlement(from_id, to_id, amount, paid_on, note)

        # --- Past payments for this period ---
        settlements_endpoint = "settlements/" if selected_period == "All time" else f"settlements/?month={selected_period}"
        settlements = get_data(settlements_endpoint, token)
        if settlements:
            with st.expander(f"Payments recorded for {label} ({len(settlements)})"):
                st_df = pd.DataFrame(settlements)
                st_df["amount"] = st_df["amount"].map(format_brl)
                st_df["settled_at"] = pd.to_datetime(st_df["settled_at"], utc=True).dt.tz_convert("America/Sao_Paulo")
                st.dataframe(
                    st_df.assign(settled_at=st_df["settled_at"].dt.strftime("%d/%m/%Y"))[
                        ["settled_at", "from_name", "to_name", "amount", "month", "note"]
                    ].rename(columns={
                        "settled_at": "Paid on", "from_name": "From", "to_name": "To",
                        "amount": "Amount", "month": "For month", "note": "Note",
                    }),
                    width="stretch", hide_index=True,
                )
                labels = {
                    row["settlement_id"]: f"{row['settled_at'].strftime('%d/%m')} – {row['from_name']} → {row['to_name']} {row['amount']}"
                    for _, row in st_df.iterrows()
                }
                target = st.selectbox("Remove a payment entered by mistake:", options=list(labels),
                                      format_func=labels.get, index=None)
                if st.button("Delete payment") and target:
                    res = requests.delete(f"{API_BASE_URL}/settlements/{target}", headers=auth_headers)
                    if res.status_code == 200:
                        st.session_state["tracker_toast"] = "Payment removed."
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")

# --- History ---------------------------------------------------------------
with history_tab:
    ui.lede(
        "Every expense you can see, newest first.",
        " That's yours plus the shared ones. To fix a mistake, delete it and add it again.",
    )
    expenditure_data = get_data("expenditures", token)

    if not expenditure_data:
        st.info("Nothing logged yet. Add your first expense in the **Add expense** tab.")
    else:
        all_expenditures_df = pd.json_normalize(expenditure_data)
        # Money arrives as JSON strings (the API uses Decimal); convert once.
        for col in ("price", "my_share"):
            if col in all_expenditures_df.columns:
                all_expenditures_df[col] = pd.to_numeric(all_expenditures_df[col])
        ts = pd.to_datetime(all_expenditures_df["transaction_timestamp"])
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        all_expenditures_df["transaction_timestamp"] = ts.dt.tz_convert("America/Sao_Paulo")
        all_expenditures_df = all_expenditures_df.sort_values(by="transaction_timestamp", ascending=False)

        def kind(row) -> str:
            text = "Shared" if row.get("is_shared") else "Personal"
            total = row.get("total_installments")
            return f"{text} · {int(total)}x" if pd.notna(total) and int(total) > 1 else text

        def column(name: str, default="—"):
            return all_expenditures_df[name] if name in all_expenditures_df else pd.Series(default, index=all_expenditures_df.index)

        # A pet-category expense names its pet, or "Both" when it was for all of them.
        pet = column("pet.name", None).where(column("pet.name", None).notna(), ALL_PETS)
        for_pets = column("category.for_pets", False).eq(True)
        what = column("category.primary_category").fillna("—") + " · " + column("category.sub_category").fillna("—")

        display_df = pd.DataFrame({
            "When": all_expenditures_df["transaction_timestamp"].dt.strftime("%d/%m/%Y %H:%M"),
            "What": what.where(~for_pets, what + " · " + pet),
            "Paid by": column("user.full_name"),
            "Type": all_expenditures_df.apply(kind, axis=1),
            "Paid with": column("payment_method.method_name"),
            "Price": all_expenditures_df["price"].map(format_brl),
            "Your part": column("my_share", 0).map(format_brl),
        })
        st.caption("**Price** is the full amount; **Your part** is what you bear of it.")
        st.dataframe(display_df, width="stretch", hide_index=True)

        with st.expander("Delete an entry"):
            delete_options = {
                row["expenditure_id"]: f"{row['transaction_timestamp'].strftime('%d/%m %H:%M')} – {format_brl(row['price'])}"
                for _, row in all_expenditures_df.iterrows()
            }
            target_id = st.selectbox("Select entry to remove:", options=delete_options.keys(),
                                     format_func=lambda x: delete_options[x], index=None)

            if st.button("Confirm delete", type="primary") and target_id:
                try:
                    res = requests.delete(f"{API_BASE_URL}/expenditures/{target_id}", headers=auth_headers)
                    if res.status_code == 200:
                        st.session_state["tracker_toast"] = f"Entry removed: {delete_options[target_id]}"
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Error deleting entry.")
                except Exception as e:
                    st.error(f"Connection error: {e}")
