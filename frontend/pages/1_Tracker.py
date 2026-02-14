import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import os

# Page Configuration
st.set_page_config(page_title="Tracker & Dashboard", page_icon="🤑", layout="wide")

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")

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
  
        st.write("---")
        is_shared = st.toggle("Shared Household Expense?", value=True, help="Leave ON if split between couple.")
        
    with col2:
        time_input = st.time_input("Time", st.session_state.selected_time)
        st.session_state.selected_time = time_input
        price = st.number_input("Price", min_value=0.0, format="%.2f")

        selected_primary, selected_sub = cascading_selectbox(
            label_primary="Category", label_secondary="Sub-Category",
            df=categories_df, col_primary="primary_category", col_secondary="sub_category"
        )
        
        st.write("---")
        is_extraordinary = st.checkbox("Extraordinary Event?", help="Outlier/Emergency expense.")
    
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
                            "nature": "Extraordinary" if is_extraordinary else "Normal",
                            "is_shared": is_shared,
                            "user_id": 0 # Backend handles this via token
                        }

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


# --- Dashboard (This can stay outside the else because it handles its own data fetch) ---
st.divider()
st.header("📈 Recent Activity")

# Fetch all expenditure data
expenditure_data = get_data("expenditures", token)

if not expenditure_data:
    st.info("No expenditures found.")
else:
    all_expenditures_df = pd.json_normalize(expenditure_data)
    
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