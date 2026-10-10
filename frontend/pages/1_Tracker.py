import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from config import API_BASE_URL

# Page Configuration
st.set_page_config(page_title="Tracker & Dashboard", page_icon="🤑", layout="wide")

# --- Authentication check ---
if "access_token" not in st.session_state or st.session_state["access_token"] is None:
    st.error("You are not logged in.")
    st.info("Please go to the **Home** page to log in.")
    st.stop()

auth_headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}

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

def cascading_selectbox(label_primary, label_secondary, df, col_primary, col_secondary, force_na_if=None, help_text_secondary=""):
    primary_options = sorted(df[col_primary].unique()) if not df.empty else []
    selected_primary = st.selectbox(label_primary, options=primary_options, index=None, placeholder=f"Select {label_primary}...")

    secondary_options = []
    disabled_secondary = True
    index_secondary = None
    dynamic_help = ""

    if selected_primary:
        if force_na_if and selected_primary == force_na_if:
            secondary_options = ["N/A"]
            disabled_secondary = True
            index_secondary = 0
            dynamic_help = f"⚠️ When selecting **{force_na_if}**, defaults to `N/A`."
        else:
            filtered_df = df[df[col_primary] == selected_primary]
            secondary_options = sorted([x for x in filtered_df[col_secondary].unique() if x])
            if secondary_options:
                disabled_secondary = False
                dynamic_help = help_text_secondary
            else:
                disabled_secondary = True

    selected_secondary = st.selectbox(
        label_secondary, options=secondary_options, index=index_secondary,
        placeholder=f"Select {label_secondary}...", disabled=disabled_secondary, help=dynamic_help
    )
    return selected_primary, selected_secondary

# --- Load Data ---
token = st.session_state["access_token"]

categories_data = get_data("categories", token)
payment_methods_data = get_data("payment_methods", token)
household_data = get_data("household_settings", token)

categories_df = pd.DataFrame(categories_data)
payment_methods_df = pd.DataFrame(payment_methods_data)

# -- Main Page UI --
st.title("💰 Expenditure Tracker")

if categories_df.empty or payment_methods_df.empty:
    st.warning("⚠️ Database missing Categories or Payment Methods! Please go to **Manage Settings** in the sidebar.")
else:
    # --- UI LOGIC STARTS HERE ---
    if "selected_time" not in st.session_state:
        user_tz = ZoneInfo("America/Sao_Paulo")

        curr_time_brl = datetime.datetime.now(user_tz)

        st.session_state.selected_time = curr_time_brl.time()

    col1, col2 = st.columns(2)

    with col1:
        date_input = st.date_input("Date", datetime.date.today(), format="DD/MM/YYYY")
        st.info("**Payer**: You (Logged-in User)")    
        
        selected_method_name, selected_institution = cascading_selectbox(
            label_primary="Payment Method", label_secondary="Institution",
            df=payment_methods_df, col_primary="method_name", col_secondary="institution", force_na_if="Cash"
        )

        # Dynamic installment logic
        current_inst = 1
        total_inst = 1

        if selected_method_name:
            matched_pm = payment_methods_df[payment_methods_df["method_name"] == selected_method_name]
            is_credit = bool(matched_pm["is_credit"].iloc[0]) if not matched_pm.empty and "is_credit" in payment_methods_df.columns else False
            if is_credit:
                st.caption("💳 Credit Card — Installments")
                st.caption("Enter an installment purchase **once**, with its full price; Tableau's cashflow datasource spreads it over the months.")
                col_inst1, col_inst2 = st.columns(2)
                total_inst = col_inst2.number_input("Total Installments", min_value=1, value=1, help="1 = paid in full. 10 = a 10x purchase.")
                current_inst = col_inst1.number_input(
                    "Installment billed this month", min_value=1, max_value=int(total_inst), value=1,
                    help="1 if you're entering it on the day you bought it; e.g. 4 if you're already paying installment 4 of 10.",
                )

  
        st.write("---")
        is_shared = st.toggle("Shared Household Expense?", value=True, help="Leave ON if split between couple.")

        # Optional per-expense override of the household ratio, sent as "shares".
        custom_shares = None
        if is_shared and household_data:
            if st.checkbox("Custom split for this expense", help="Override the household ratio just for this one, e.g. 70/30, or 100% on one person."):
                share_cols = st.columns(len(household_data))
                custom_shares = []
                for share_col, member in zip(share_cols, household_data):
                    name = member["user"].get("full_name") or member["user"]["email"]
                    pct = share_col.number_input(
                        f"{name} %", min_value=0, max_value=100, step=5,
                        value=int(round(float(member["share_pct"]) * 100)), key=f"share_{member['user_id']}",
                    )
                    custom_shares.append((member["user_id"], pct))
                split_total = sum(pct for _, pct in custom_shares)
                if split_total != 100:
                    st.warning(f"Shares add up to {split_total}%, not 100%.")
        
    with col2:
        time_input = st.time_input("Time", st.session_state.selected_time)
        st.session_state.selected_time = time_input
        price = st.number_input("Price", min_value=0.0, format="%.2f", help="For an installment purchase, the full price, not one installment.")

        selected_primary, selected_sub = cascading_selectbox(
            label_primary="Category", label_secondary="Sub-Category",
            df=categories_df, col_primary="primary_category", col_secondary="sub_category"
        )
        
        st.write("---")
        nature_option = st.radio(
            "Nature",
            options=["Normal", "Extraordinary", "Recurring", "Annual"],
            index=0,
            horizontal=True,
            help="Normal: everyday | Extraordinary: unplanned/emergency | Recurring: monthly subscription | Annual: once-a-year (IPVA, IPTU)"
        )
    
        # --- Submit button ---
        if categories_df.empty or payment_methods_df.empty:
            st.warning("Cannot sumbit: Missing **Categories** or **Payment Method**.")
        else:
            if st.button("Submit Expenditure", type="primary"):

                # 1. Validation
                missing_fields = []
                if not selected_method_name: missing_fields.append("Payment Method")
                if not selected_institution: missing_fields.append("Institution")
                if not selected_primary: missing_fields.append("Category")
                if not selected_sub: missing_fields.append("Sub-Category")
                if price <= 0: missing_fields.append("Price (must be > $ 0)")
                if custom_shares is not None and sum(pct for _, pct in custom_shares) != 100:
                    missing_fields.append("Custom split (must add up to 100%)")

                if missing_fields:
                    st.error(f"⚠️ Please fill out: **{', '.join(missing_fields)}**")
                else:
                    try:
                        # 2. Lookups
                        matched_method = payment_methods_df[
                            (payment_methods_df["method_name"] == selected_method_name) &
                            (payment_methods_df["institution"].fillna("N/A") == (selected_institution if selected_institution else "N/A"))
                        ]
                        payment_method_id = matched_method["payment_method_id"].iloc[0]

                        category_id = categories_df[
                            (categories_df["primary_category"] == selected_primary) &
                            (categories_df["sub_category"] == selected_sub)
                        ]["category_id"].iloc[0]

                        # 3. Payload
                        dt_naive = datetime.datetime.combine(date_input, time_input)

                        user_tz = ZoneInfo("America/Sao_Paulo")
                        dt_aware = dt_naive.replace(tzinfo=user_tz)

                        payload = {
                            "transaction_timestamp": dt_aware.isoformat(),
                            "price": price,
                            "category_id": int(category_id),
                            "payment_method_id": int(payment_method_id),
                            "nature": nature_option,
                            "is_shared": is_shared,
                            "user_id": 0, # Backend handles this via token
                            "current_installment": current_inst,
                            "total_installments": total_inst
                        }
                        if custom_shares is not None:
                            # People at 0% simply bear none of it, so they get no row.
                            payload["shares"] = [
                                {"user_id": uid, "share_pct": f"{pct / 100:.2f}"} for uid, pct in custom_shares if pct > 0
                            ]

                        # 4. Request
                        response = requests.post(f"{API_BASE_URL}/expenditures/", json=payload, headers=auth_headers)
                        if response.status_code == 200:
                            st.success("Expenditure added successfully! ✅")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Error: {response.status_code} – {response.text}")
                    except Exception as e:
                        st.error(f"Error processing request: {e}")


# --- Monthly overview: my summary + who owes whom, driven by one period picker ---
st.divider()
st.header("📊 Monthly Overview")

today_brl = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).date()
month_options = []
y, m = today_brl.year, today_brl.month
for _ in range(12):
    month_options.append(f"{y:04d}-{m:02d}")
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
month_options.append("All time")

selected_period = st.selectbox(
    "Period", options=month_options, index=0,
    format_func=lambda p: p if p == "All time" else datetime.date(int(p[:4]), int(p[5:]), 1).strftime("%B %Y"),
    help="Amounts use the household ratio that applied when each expense was logged.",
)


def brl(value) -> str:
    return f"R$ {float(value):,.2f}"


if selected_period == "All time":
    st.caption("Pick a month to see your spending summary.")
else:
    summary = get_data(f"summary/?month={selected_period}", token)
    if summary:
        me, household = summary["me"], summary["household_shared"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "My spending", brl(me["total"]),
            delta=f"{float(me['total']) - float(me['previous_total']):+,.2f} vs {summary['previous_month']}",
            delta_color="inverse",
            help="Your share of shared expenses plus your personal ones.",
        )
        m2.metric("My share of shared", brl(me["shared_share"]))
        m3.metric("My personal", brl(me["personal"]))
        m4.metric(
            "Household shared total", brl(household["total"]),
            delta=f"{float(household['total']) - float(household['previous_total']):+,.2f} vs {summary['previous_month']}",
            delta_color="inverse",
            help="Full price of shared expenses this month, whoever paid.",
        )

        if summary["by_category"]:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.caption("My spending by category")
                cat_df = pd.DataFrame(summary["by_category"]).rename(columns={"label": "Category", "amount": "Amount"})
                cat_df["Amount"] = pd.to_numeric(cat_df["Amount"])
                st.bar_chart(cat_df, x="Category", y="Amount", horizontal=True, sort="-Amount")
            with c2:
                st.caption("Fixed vs variable")
                ct_df = pd.DataFrame(summary["by_cost_type"]).rename(columns={"label": "Cost Type", "amount": "Amount"})
                ct_df["Amount"] = pd.to_numeric(ct_df["Amount"])
                total = ct_df["Amount"].sum()
                ct_df["Share"] = ct_df["Amount"] / total * 100 if total else 0
                st.dataframe(
                    ct_df, width="stretch", hide_index=True,
                    column_config={
                        "Amount": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Share": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
                    },
                )
        else:
            st.info("You have no spending logged for this month yet.")

st.subheader("⚖️ Who Owes Whom")
balance_endpoint = "balances/" if selected_period == "All time" else f"balances/?month={selected_period}"
balance_report = get_data(balance_endpoint, token)

if balance_report:
    if balance_report["transfers"]:
        for t in balance_report["transfers"]:
            st.success(f"**{t['from_name']}** owes **{t['to_name']}** R$ {float(t['amount']):,.2f}")
    else:
        st.info("All square — nobody owes anything for this period.")

    balance_df = pd.DataFrame(balance_report["members"])
    if not balance_df.empty:
        money_cols = {
            "paid": "Paid", "borne": "Their Share",
            "settled_out": "Paid Back", "settled_in": "Received", "net": "Net (+ is owed)",
        }
        for col in money_cols:
            balance_df[col] = pd.to_numeric(balance_df[col])
        st.dataframe(
            balance_df[["full_name", *money_cols]].rename(columns={"full_name": "Person", **money_cols}),
            width="stretch", hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="R$ %.2f") for c in money_cols.values()},
        )

    # --- Record a payment between the two of you ---
    members = {m["user_id"]: m["full_name"] for m in balance_report["members"]}
    suggestion = balance_report["transfers"][0] if balance_report["transfers"] else None
    period_label = "the running all-time balance" if selected_period == "All time" else selected_period

    if len(members) >= 2:
        with st.expander("💸 Record a payment", expanded=False):
            st.caption(f"Squares up **{period_label}**. Pre-filled with what's currently owed.")
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
                amount = f3.number_input(
                    "Amount", min_value=0.0, format="%.2f",
                    value=float(suggestion["amount"]) if suggestion else 0.0,
                )
                paid_on = f4.date_input("Paid on", today_brl, format="DD/MM/YYYY")
                note = st.text_input("Note (optional)", placeholder="e.g. Pix transfer")

                if st.form_submit_button("Record Payment", type="primary"):
                    if from_id == to_id:
                        st.error("⚠️ From and To must be different people.")
                    elif amount <= 0:
                        st.error("⚠️ Amount must be greater than zero.")
                    else:
                        now_brl = datetime.datetime.now(ZoneInfo("America/Sao_Paulo"))
                        payload = {
                            "settled_at": datetime.datetime.combine(paid_on, now_brl.time(), tzinfo=ZoneInfo("America/Sao_Paulo")).isoformat(),
                            "from_user_id": from_id,
                            "to_user_id": to_id,
                            "amount": f"{amount:.2f}",
                            "month": None if selected_period == "All time" else selected_period,
                            "note": note or None,
                        }
                        res = requests.post(f"{API_BASE_URL}/settlements/", json=payload, headers=auth_headers)
                        if res.status_code == 200:
                            st.success("Payment recorded! ✅")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")

    # --- Past payments for this period ---
    settlements_endpoint = "settlements/" if selected_period == "All time" else f"settlements/?month={selected_period}"
    settlements = get_data(settlements_endpoint, token)
    if settlements:
        with st.expander(f"🧾 Payments recorded ({len(settlements)})"):
            st_df = pd.DataFrame(settlements)
            st_df["amount"] = pd.to_numeric(st_df["amount"])
            st_df["settled_at"] = pd.to_datetime(st_df["settled_at"], utc=True).dt.tz_convert("America/Sao_Paulo")
            st.dataframe(
                st_df.assign(settled_at=st_df["settled_at"].dt.strftime("%d/%m/%Y"))[
                    ["settled_at", "from_name", "to_name", "amount", "month", "note"]
                ].rename(columns={
                    "settled_at": "Paid On", "from_name": "From", "to_name": "To",
                    "amount": "Amount", "month": "For Month", "note": "Note",
                }),
                width="stretch", hide_index=True,
                column_config={"Amount": st.column_config.NumberColumn(format="R$ %.2f")},
            )
            labels = {
                row["settlement_id"]: f"{row['settled_at'].strftime('%d/%m')} – {row['from_name']} → {row['to_name']} R$ {row['amount']:,.2f}"
                for _, row in st_df.iterrows()
            }
            target = st.selectbox("Remove a payment entered by mistake:", options=list(labels), format_func=labels.get, index=None)
            if st.button("Delete Payment") and target:
                res = requests.delete(f"{API_BASE_URL}/settlements/{target}", headers=auth_headers)
                if res.status_code == 200:
                    st.success("Payment removed.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Error: {res.status_code} – {res.json().get('detail', res.text)}")

# --- Dashboard (This can stay outside the else because it handles its own data fetch) ---
st.divider()
st.header("📈 Recent Activity")

# Fetch all expenditure data
expenditure_data = get_data("expenditures", token)

if not expenditure_data:
    st.info("No expenditures found.")
else:
    all_expenditures_df = pd.json_normalize(expenditure_data)
    # Prices arrive as JSON strings as the API currently uses Decimal.
    # Convert it once so every consumer gets a real number.
    if "price" in all_expenditures_df.columns:
        all_expenditures_df["price"] = pd.to_numeric(all_expenditures_df["price"])
    if "transaction_timestamp" in all_expenditures_df.columns:
        all_expenditures_df["transaction_timestamp"] = pd.to_datetime(all_expenditures_df["transaction_timestamp"])
        
        if all_expenditures_df["transaction_timestamp"].dt.tz is None:
            all_expenditures_df["transaction_timestamp"] = all_expenditures_df["transaction_timestamp"].dt.tz_localize("UTC")

        all_expenditures_df["transaction_timestamp"] = all_expenditures_df["transaction_timestamp"].dt.tz_convert("America/Sao_Paulo")    
        all_expenditures_df = all_expenditures_df.sort_values(by="transaction_timestamp", ascending=False)

    cols_to_display = {
        "transaction_timestamp": "Timestamp",
        "user.full_name": "Paid By",
        "category.primary_category": "Category",
        "category.sub_category": "Sub-Category",
        "nature": "Nature",
        "is_shared": "Shared?",
        "payment_method.method_name": "Payment Method",
        "price": "Price",
    }
    valid_cols = {k: v for k, v in cols_to_display.items() if k in all_expenditures_df}
    
    if valid_cols:
        display_df = all_expenditures_df[valid_cols.keys()].rename(columns=valid_cols)
        display_df["Timestamp"] = pd.to_datetime(display_df["Timestamp"]).dt.strftime("%d/%m/%Y %H:%M")
        if "Shared?" in display_df.columns:
            display_df["Shared?"] = display_df["Shared?"].apply(lambda x: "✅ Yes" if x else "👤 No")
        
        st.dataframe(display_df, width="stretch")

        # Delete Utility
        with st.expander("🗑️ Delete an Entry"):
            delete_options = {
                row["expenditure_id"]: f"{row['transaction_timestamp'].strftime('%d/%m %H:%M')} - ${row['price']:.2f}"
                for _, row in all_expenditures_df.iterrows()
            }
            target_id = st.selectbox("Select entry to remove:", options=delete_options.keys(), format_func=lambda x: delete_options[x], index=None)
            
            if st.button("Confirm Delete", type="primary") and target_id:
                try:
                    res = requests.delete(f"{API_BASE_URL}/expenditures/{target_id}", headers=auth_headers)
                    if res.status_code == 200:
                        st.success("Entry removed!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Error deleting entry.")
                except Exception as e:
                    st.error(f"Connection error: {e}")