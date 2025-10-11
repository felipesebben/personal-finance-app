import streamlit as st
import requests
import datetime
import pandas as pd

# Page Configuration
st.set_page_config(
    page_title="Expenditure Tracker",
    page_icon="🤑",
    layout="centered"
)


API_BASE_URL = "http://localhost:8000"

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
    
# Fetch the dimension data
people_data = get_data("people")
categories_data = get_data("categories")
payment_methods_data = get_data("payment_methods")

# Convert lists of dicts to DataFrames for easier handling
people_df = pd.DataFrame(people_data)
categories_df = pd.DataFrame(categories_data)
payment_methods_df = pd.DataFrame(payment_methods_data)

# -- Main Page UI --
st.title("💰 Personal Expenditure Tracker")

# Form for New Expenditure
st.header("Add a New Expenditure")

with st.form("expenditure_form", clear_on_submit=True):
    # Use columns to organize the form
    col1, col2 = st.columns(2)

    with col1:
        date_input = st.date_input("Date", datetime.date.today(), format="DD/MM/YYYY")

        # Dropdown for Person
        person_name = st.selectbox(
            "Person",
            options=people_df["person_name"],
            index=None,
            placeholder="Select a person..."
        ) 

        # Dropdown for Payment Method
        payment_method_name = st.selectbox(
            "Payment Method",
            options=payment_methods_df["method_name"],
            index=None,
            placeholder="Select a payment method..."
        )
        
    with col2:
        time_input = st.time_input("Time", datetime.datetime.now().time())
        price = st.number_input("Price", min_value=0.0, format="%.2f")

        # Dropdown for Category
        # We'll create a user-friendly name for the dropdown
        categories_df["display_name"] = categories_df["primary_category"] + " – " + categories_df["sub_category"]
        category_display_name = st.selectbox(
            "Category",
            options=categories_df["display_name"],
            index=None,
            placeholder="Select a category..."
        )

    
    # Submit button for the form
    submitted = st.form_submit_button("Submit Expenditure")

if submitted:
    # -- Data Validation --
    if not all([person_name, payment_method_name, category_display_name, price > 0]):
        st.warning("Please fill out all fields.")
    else:
        #  Find the IDs corresponding to the selected names
        person_id = people_df[people_df["person_name"] == person_name]["person_id"].iloc[0]
        category_id = categories_df[categories_df["display_name"] == category_display_name]["category_id"].iloc[0]
        payment_method_id = payment_methods_df[payment_methods_df["method_name"] == payment_method_name]["payment_method_id"].iloc[0]
    
        # Combine date and time into single datetime object
        transaction_timestamp = datetime.datetime.combine(date_input, time_input)

        # Prepare the data payload in the format expected by the API
        payload = {
            "transaction_timestamp": transaction_timestamp.isoformat(),
            "price": price,
            "person_id": int(person_id),
            "category_id": int(category_id),
            "payment_method_id": int(payment_method_id)
        }


        try:
            # Send the POST request to the backend
            response = requests.post(f"{API_BASE_URL}/expenditures/", json=payload)

            # Check the response from the server
            if response.status_code == 200:
                st.success("Expenditure added successfully! ✅")
            else:
                # Show error details if something went wrong
                st.error(f"Error: {response.status_code} – {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("Connection Error: Could not connect to the API. Is the backend running?")

