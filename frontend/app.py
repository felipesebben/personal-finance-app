import streamlit as st
import requests
import datetime

# Page Configuration
st.set_page_config(
    page_title="Expenditure Tracker",
    page_icon="🤑",
    layout="centered"
)

st.title("💰 Personal Expenditure Tracker")

# Form for New Expenditure
st.header("Add a New Expenditure")

with st.form("expenditure_form", clear_on_submit=True):
    # Use columns to organize the form
    col1, col2 = st.columns(2)

    with col1:
        date_input = st.date_input("Date", datetime.date.today(), format="DD/MM/YYYY")
        # Use number inputs as IDs for now - #TODO for later on
        person_id = st.number_input("Person ID", min_value=1, step=1)
        payment_method_id = st.number_input("Payment Method ID", min_value=1, step=1)

    with col2:
        time_input = st.time_input("Time", datetime.datetime.now().time())
        price = st.number_input("Price", min_value=0.0, format="%.2f")
        category_id = st.number_input("Category ID", min_value=1, step=1)
    
    # Submit button for the form
    submitted = st.form_submit_button("Submit Expenditure")

    if submitted:
        # Combine date and time into single datetime object
        transaction_timestamp = datetime.datetime.combine(date_input, time_input)

        # Prepare the data payload in the format expected by the API
        payload = {
            "transaction_timestamp": transaction_timestamp.isoformat(),
            "price": price,
            "person_id": person_id,
            "category_id": category_id,
            "payment_method_id": payment_method_id
        }

        # Define the API endpoint
        API_URL = "http://localhost:8000/expenditures/"

        try:
            # Send the POST request to the backend
            response = requests.post(API_URL, json=payload)

            # Check the response from the server
            if response.status_code == 200:
                st.success("Expenditure added successfully! ✅")
            else:
                # Show error details if something went wrong
                st.error(f"Error: {response.status_code} – {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("Connection Error: Could not connect to the API. Is the backend running?")

