import streamlit as st
import requests
import os

st.set_page_config(page_title="Manage Settings", page_icon="⚙️", layout="wide")

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")

# --- Authentication Check ---
# If the user lands here without logging in, stop them.
if "access_token" not in st.session_state or st.session_state["access_token"] is None:
    st.error("You are not logged in.")
    st.info("Please go to the **Home** page to log in.", icon=":material/info:")
    st.stop()

# Prepare headers for API calls
auth_headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
            
# --- Helper Functions ---

def send_post_request(endpoint: str, payload: dict, success_message: str):
    """
    Sends a POST request to the specified API endpoint with authentication headers

    
    :param endpoint: The API route endpoint (e.g., "categories).
    :type endpoint: str
    :param payload: The dictionary containing data to be sent.
    :type payload: dict
    :param success_message: The message to display upon successful creation.
    :type success_message: str
    :return: None
    """
    try:
        # Add headers
        response = requests.post(f"{API_BASE_URL}/{endpoint}/", json=payload, headers=auth_headers)
        if response.status_code == 200:
            st.success(success_message)
            st.cache_data.clear()
            st.rerun() # Updates the list immediately
        elif response.status_code == 401:
            st.error("Session Expired. Please log in again.")
        elif response.status_code == 409:
            st.error("Error: This item already exists.")
        elif response.status_code == 500:
            # Creates a more meaningful error message if tried to duplicate.
            st.error("Internal Server Error: Something went wrong on the server.")
        else:
            st.error(f"Error: {response.status_code}: – {response.text}")
    except requests.exceptions.ConnectionError:
        st.error("Connection Error: Could not connect to the API.")

def delete_item(endpoint: str, item_id: int):
    """
    Sends a DELETE request to remove an item by ID.
    
    :param endpoint: The API route endpoint (e.g., "categories").
    :type endpoint: str
    :param item_id: The unique identifier of the item to delete.
    :type item_id: int
    :return: None
    """
    try:
        response = requests.delete(f"{API_BASE_URL}/{endpoint}/{item_id}", headers=auth_headers)
        if response.status_code == 200:
            st.success("Item deleted!")
            st.cache_data.clear()
            st.rerun()
        elif response.status_code == 401:
            st.error("Session Expired. Please log in again.")
        else:
            st.error(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        st.error(f"Request failed: {e}")

@st.cache_data
def get_data(endpoint: str, token:str):
    """
    Fetches data from the API with authentication headers.
    
    :param endpoint: The API route endpoint (e.g., "users").
    :type endpoint: str
    :param token: The Bearer token for authentication.
    :type token: str
    :return: A list of records from the API, or an empty list on failure.
    :rtype: list
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}/", headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.warning("Session expired. Data could not be loaded.")
            return []
        else:
            return []
    except requests.exceptions.RequestException:
        return []
    
# --- Main UI ---

st.title("⚙️ Manage Settings")
st.info("Use this page to add new Users, Categories, or Payment Methods.")

# Fetch data
users = get_data("users", st.session_state["access_token"])
categories = get_data("categories", st.session_state["access_token"])
payment_methods = get_data("payment_methods", st.session_state["access_token"])

col1, col2, col3 = st.columns(3)

# Column 1: Users
with col1:
    st.subheader("Add User")
    with st.form("add_user", clear_on_submit=True):
        new_name = st.text_input("Name")
        new_email = st.text_input("Email")
        new_pass = st.text_input("Password", type="password")
        submit_user = st.form_submit_button("Add Person")

        if submit_user and new_email and new_name:
            payload = {
                "full_name": new_name,
                "email": new_email,
                "password": new_pass
            }
            send_post_request("users", payload, f"Added user {new_name}!")
        elif submit_user:
            st.warning("Please fill in all fields(Name, Email, and Password).")

    st.divider()
    st.caption("Existing Users")
    if users:
        for u in users:
            c1, c2 = st.columns([4, 1])
            c1.text(f"{u['full_name']} ({u['email']})")
            
            if c2.button("🗑️", key=f"del_u_{u['user_id']}"):
                delete_item("users", u['user_id'])

# Column 2: Categories
with col2:
    st.subheader("Add Category")
    with st.form("add_category", clear_on_submit=True):
        new_primary = st.text_input("Primary Category (e.g., Food)")
        new_sub = st.text_input("Sub Category (e.g., Groceries)")
        
        # 2.1 Capture the user's choice
        new_type = st.radio("Cost Type", ["Variable", "Fixed"], horizontal=True)

        if st.form_submit_button("Add") and new_sub and new_primary:
            payload = {
                "primary_category": new_primary,
                "sub_category": new_sub,
                "cost_type": new_type,
            }
            send_post_request("categories", payload, f"Added {new_primary} – {new_sub}!")


    st.divider()
    st.caption("Existing Categories")
    # Sort items so they don't look random
    if categories:
        sorted_cats = sorted(categories, key=lambda x: (x["primary_category"], x["sub_category"]))
        for c in sorted_cats:
            c1, c2 = st.columns([4, 1])
            # Display formatted as 'primary > sub (type)'
            cost_type_short = c.get("cost_type", "?")[0] if c.get("cost_type") else "?"
            c1.text(f"{c['primary_category']} > {c['sub_category']} ({c.get('cost_type', '?')[0]})")
            
            if c2.button("🗑️", key=f"del_c_{c['category_id']}"):
                delete_item("categories", c["category_id"])

# Column 3: Payment Methods
with col3:
    st.subheader("Payment Method")
    with st.form("add_method", clear_on_submit=True):
        new_method = st.text_input("Method Name")
        new_inst = st.text_input("Institution")
        submit_method = st.form_submit_button("Add Method")

        if submit_method and new_method:
            payload = {
                "method_name": new_method,
                "institution": new_inst,
            }
            send_post_request("payment_methods", payload, f"Added {new_method}!")   
    
    st.divider()
    st.caption("Existing Methods")
    for pm in payment_methods:
        c1, c2 = st.columns([4, 1])
        c1.text(f"{pm['method_name']} {pm['institution']}")
        if c2.button("🗑️", key=f"del_pm_{pm['payment_method_id']}"):
            delete_item("payment_methods", pm["payment_method_id"])

# --- ETL Trigger ---
st.divider()
st.header("Data Synchronization")
st.info("Click the button below to manually trigger the ETL pipeline. This will extract data from the database, generate the Hyper file, and publish it to Tableau.")

if st.button("Run ETL Pipeline", type="primary"):
    with st.spinner("Pipeline running... (This may take a moment)"):
        try:
            # Add headers
            # Use the /refresh endpoint in backend
            response = requests.post(f"{API_BASE_URL}/refresh", headers=auth_headers)

            if response.status_code == 200:
                data = response.json()
                st.success("ETL Finished Successfully!")
                st.json(data)
            elif response.status_code == 401:
                st.error("Session Expired. Please log in again.")
            else:
                st.error(f"Server Error: ({response.status_code})")
                st.code(response.text)
        
        except requests.exceptions.ConnectionError:
            st.error("Connection Failed")
            st.warning(f"Could not reach the backend at `{API_BASE_URL}`. Is the Docker container running?")