import streamlit as st
import requests
import datetime
import pandas as pd
import os

# Page Configuration
st.set_page_config(
    page_title="Tracker & Dashboard",
    page_icon="🤑",
    layout="wide"
)


API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")

# Helper functions to fetch data from API

# We use st.cache_data to avoid re-fetching on every interaction
@st.cache_data
def get_data(endpoint: str):
    """
    Generic function to fetch data from an API endpoint.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch {endpoint}. Status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error(f"Connection Error: Could not connect to the API to fetch {endpoint}.")
        return []
    

# 1. Load Data
# Fetch the dimension data
people_data = get_data("people")
categories_data = get_data("categories")
payment_methods_data = get_data("payment_methods")

# Convert to DataFrames
people_df = pd.DataFrame(people_data)
categories_df = pd.DataFrame(categories_data)
payment_methods_df = pd.DataFrame(payment_methods_data)

# -- Main Page UI --
st.title("💰 Expenditure Tracker")


if people_df.empty or categories_df.empty or payment_methods_df.empty:
    st.warning("⚠️ Your database is empty! Please go to **Manage Settings** in the sidebar to add People, Categories, and Payment Methods first.")
else:
    # Session state initialization
    # We only set the 'initial' time once the app first loads
    if "selected_time" not in st.session_state:
        st.session_state.selected_time = datetime.datetime.now().time()

    col1, col2 = st.columns(2)

    with col1:
        date_input = st.date_input("Date", datetime.date.today(), format="DD/MM/YYYY")

        
        # Safe to access to columns
        # Dropdown for Person. Who paid? (Cash Flow)
        person_name = st.selectbox(
            "Who Paid?",
            options=people_df["person_name"] if not people_df.empty else [],
            index=None,
            placeholder="Select Payer..."
        ) 

        # Cascading payment dropdowns
        # 1. Get unique Payment Types (e.g., Credit Card, Pix, Cash)
        unique_methods = sorted(payment_methods_df["method_name"].unique()) if not payment_methods_df.empty else []
        
        # Dropdown for Payment Options
        selected_method_name = st.selectbox(
            "Payment Method",
            options=unique_methods,
            index=None,
            placeholder="Select Method..."
        )

        # 2. Filter Institutions based on selection
        if selected_method_name:
            filtered_insts = payment_methods_df[payment_methods_df["method_name"] == selected_method_name]
            # Handle cases where institution might be None/Empty
            inst_options = sorted([i for i in filtered_insts["institution"].unique() if i])
        
            # Logic for Cash:
            # If the user chose "Cash", force the option to be "N/A".
            if selected_method_name == "Cash":
                inst_options = ["N/A"]
                disabled_inst = True
                default_index = 0
            else:
                disabled_inst = False if inst_options else True
                default_index = None

        else:
            inst_options = []
            disabled_inst = True
            default_index = None

        help_msg = "⚠️ When selecting **Cash**, defaults to `N/A`." if selected_method_name == "Cash" else ""
        
        selected_institution = st.selectbox(
            "Institution",
            options=inst_options,
            index=default_index,
            placeholder="Select Institution...",
            disabled=disabled_inst,
            help=help_msg
        )
        # New flag: Shared Expense
        st.write("---")
        is_shared = st.toggle("Shared Household Expense?", value=True,
                              help="Leave this ON if this cost is split between the couple. Turn OFF for personal expenses.")
        
    with col2:
        # Use this session state to keep the time stable
        time_input = st.time_input("Time", st.session_state.selected_time)

        # When the user manually changes the time, we update our 'notepad'
        st.session_state.selected_time = time_input

        price = st.number_input("Price", min_value=0.0, format="%.2f")

        # Cascading Dropdowns
        # 1. Get unique Primary Categories, sorted alphabetically
        primary_categories = sorted(categories_df["primary_category"].unique()) if not categories_df.empty else []

        selected_primary = st.selectbox(
            "Category",
            options=primary_categories,
            index=None,
            placeholder="Select Category..."
        )

        # 2. Filter Sub-categories based on selection
        if selected_primary:
            # Filter the DataFrame to only rows matching the selected primary
            filtered_subs = categories_df[categories_df["primary_category"] == selected_primary]
            sub_options = sorted(filtered_subs["sub_category"].unique())
            disabled_sub = False
        else:
            sub_options = []
            disabled_sub = True # Lock the box if no primary is selected
        selected_sub = st.selectbox(
            "Sub-Category",
            options=sub_options,
            index=None,
            placeholder="Select Sub-Category...",
            disabled=disabled_sub
        )

        # Nature checkbox
        st.write("---")
        is_extraordinary = st.checkbox("Extraordinary Event? ",
                                       help="Check this if the expense is an uxpected outlier (e.g., emergency repair).")
    
# Submit button for the form
if st.button("Submit Expenditure", type="primary"):

    # 1. Create a list to catch culprits
    missing_fields = []

    # 2. Check each field individually
    if not person_name:
        missing_fields.append("Who Paid")
    
    if not selected_method_name:
        missing_fields.append("Payment Method")
    
    if not selected_institution:
        missing_fields.append("Institution")

    if not selected_primary:
        missing_fields.append("Category")
    
    if not selected_sub:
        missing_fields.append("Sub-Category")

    if price <=0:
        missing_fields.append("Price (must be < $ 0)")

    # 3. Decision Time
    if missing_fields:
        # Join the list into a string
        error_msg = ", ".join(missing_fields)
        st.error(f"⚠️ Please fill out the following fields: **{error_msg}**")
    else:
         #  Find the IDs corresponding to the selected names
        person_id = people_df[people_df["person_name"] == person_name]["person_id"].iloc[0]
        
        # Payment method lookup
        # Look for a match on both Name and Institution
        # Because we forced "N/A" in the UI for Cash, this will find the correct DB record.
        try:
            matched_method = payment_methods_df[
                (payment_methods_df["method_name"] == selected_method_name) &
                (payment_methods_df["institution"].fillna("N/A") == (selected_institution if selected_institution else "N/A"))
            ]
            if not matched_method.empty:
                payment_method_id = matched_method["payment_method_id"].iloc[0]
            else:
                # Last resort fallback if the combination isn't found
                st.error(f"Could not find payment method: {selected_method_name} at {selected_institution}")
                st.stop()
        except IndexError:
            st.error("Payment method lookup failed.")
            st.stop
        
        # Smart lookup: Find the ID where both primary and sub match
        category_id = categories_df[
            (categories_df["primary_category"] == selected_primary) &
            (categories_df["sub_category"] == selected_sub)
        ]["category_id"].iloc[0]
        
        # Combine date and time into single datetime object
        transaction_timestamp = datetime.datetime.combine(date_input, time_input)

        nature_value = "Extraordinary" if is_extraordinary else "Normal"
        # Prepare the data payload in the format expected by the API
        payload = {
            "transaction_timestamp": transaction_timestamp.isoformat(),
            "price": price,
            "person_id": int(person_id),
            "category_id": int(category_id),
            "payment_method_id": int(payment_method_id),
            "nature": nature_value,
            "is_shared": is_shared
        }


        try:
            # Send the POST request to the backend
            response = requests.post(f"{API_BASE_URL}/expenditures/", json=payload)

            # Check the response from the server
            if response.status_code == 200:
                st.success("Expenditure added successfully! ✅")
                # Clear the cache so the dashboard updates
                st.cache_data.clear()
            else:
                # Show error details if something went wrong
                st.error(f"Error: {response.status_code} – {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("Connection Error: Could not connect to the API. Is the backend running?")

# 3. Dashboard
st.divider()
st.header("📈 Recent Activity")

# Helper to delete
def delete_expenditure(exp_id):
    try:
        res = requests.delete(f"{API_BASE_URL}/expenditures/{exp_id}")
        if res.status_code == 200:
            st.success("Deleted")
            st.cache_data.clear()
        else:
            st.error("Could not delete.")
    except:
        st.error("Connection error")

# Fetch all expenditure data
expenditure_data = get_data("expenditures")

if not expenditure_data:
    st.info("No expenditures found.")
else:
    # Convert to DataFrame for sorting, but iterate for display
    all_expenditures_df = pd.json_normalize(expenditure_data)

    # Sort by date (most recent first)
    if "transaction_timestamp" in all_expenditures_df.columns:
        all_expenditures_df["transaction_timestamp"] = pd.to_datetime(all_expenditures_df["transaction_timestamp"])
        all_expenditures_df = all_expenditures_df.sort_values(by="transaction_timestamp", ascending=False)
    

    # Define which columns we want to display and give them friendly names
    cols_to_display = {
        "transaction_timestamp": "Timestamp",
        "person.person_name": "Paid By",
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

        # Convert to DAtetime objects (so we can sort correctly)
        display_df["Timestamp"] = pd.to_datetime(display_df["Timestamp"])

        # Sort by Date (most recent first)
        display_df = display_df.sort_values(by="Timestamp", ascending=False)

        # Format to desired timestamp format
        display_df["Timestamp"] = display_df["Timestamp"].dt.strftime("%d/%m/%Y %H:%M")
        
        # Clean booleans for display
        if "Shared?" in display_df.columns:
            display_df["Shared?"] = display_df["Shared?"].apply(lambda x: "✅ Yes" if x else "👤 No")
        st.dataframe(display_df, width="stretch")

        # Simple Delete Utility
        with st.expander("🗑️ Delete an Entry"):
            # Create a list of descriptions for the dropdown so you know what we are deleting.
            # Example: "30/12 15:30 – $50.00 (Groceries)"
            delete_options = {
                row["expenditure_id"]: f"{row["transaction_timestamp"].strftime("%d/%m %H:%M")} - ${row["price"]:.2f} ({row["category.sub_category"]})"
                for _, row in all_expenditures_df.iterrows()
            }

            target_id = st.selectbox(
                "Select entry to remove:",
                options=delete_options.keys(),
                format_func=lambda x: delete_options[x],
                index=None,
                placeholder="Chose one..."
            )

            if st.button("Confirm Delete", type="primary") and target_id:
                try:
                    res = requests.delete(f"{API_BASE_URL}/expenditures/{target_id}")
                    if res.status_code == 200:
                        st.success("Entry removed!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Error deleting entry.")
                except Exception as e:
                    st.error(f"Connection error: {e}")

    else:
        st.write("Data received but unexpected format.")
 
