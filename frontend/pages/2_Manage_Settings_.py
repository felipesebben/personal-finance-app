import streamlit as st
import requests
import os

st.set_page_config(page_title="Manage Settings", page_icon="⚙️", layout="wide")

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")

def send_post_request(endpoint: str, payload: dict, success_message: str):
    """
    Generic helper to send POST requests
    """
    try:
        response = requests.post(f"{API_BASE_URL}/{endpoint}/", json=payload)
        if response.status_code == 200:
            st.success(success_message)
            # Clear the cache so that the main page re-fetches the new data next time
            st.cache_data.clear()
            st.rerun() # Updates the list immediately
        elif response.status_code == 500:
            # Creates a more meaningful error message if tried to duplicate.
            st.error("Error: Could not add item. It might already exist.")
        else:
            st.error(f"Error: {response.status_code}: – {response.text}")
    except requests.exceptions.ConnectionError:
        st.error("Connection Error: Could not connect to the API.")

def delete_item(endpoint: str, item_id: int):
    try:
        response = requests.delete(f"{API_BASE_URL}/{endpoint}/{item_id}")
        if response.status_code == 200:
            st.success("Item deleted!")
            st.cache_data.clear()
            st.rerun() # Refresh the page instantly
        else:
            st.error(f"Error: {response.text}")
    except Exception as e:
        st.error(f"Error: {e}")

@st.cache_data
def get_data(endpoint):
    try:
        return requests.get(f"{API_BASE_URL}/{endpoint}/").json()
    except:
        return []
    

st.title("⚙️ Manage Settings")
st.info("Use this page to add new people, categories, or payment methods, to your system.")

# Fetch data
people = get_data("people")
categories = get_data("categories")
payment_methods = get_data("payment_methods")

col1, col2, col3 = st.columns(3)

# Column 1: People
with col1:
    st.subheader("Add Person")
    with st.form("add_person", clear_on_submit=True):
        new_person = st.text_input("Name")
        submit_person = st.form_submit_button("Add Person")

        if submit_person and new_person:
            send_post_request("people", {"person_name": new_person}, f"Added {new_person}!")

    st.divider()
    st.caption("Existing People")
    for p in people:
        c1, c2 = st.columns([4, 1])
        c1.text(p["person_name"])
        if c2.button("🗑️", key=f"del_p_{p["person_id"]}"):
            delete_item("people", p["person_id"])

# Column 2: Categories
with col2:
    st.subheader("Add Category")
    with st.form("add_category", clear_on_submit=True):
        new_primary = st.text_input("Primary Category (e.g., Food)")
        new_sub = st.text_input("Sub Category (e.g., Groceries)")
        
        # 1. Capture the user's choice
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
            c1.text(f"{c["primary_category"]} > {c["sub_category"]} ({c.get('cost_type', '?')[0]})")
            
            if c2.button("🗑️", key=f"del_c_{c["category_id"]}"):
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
        c1.text(f"{pm["method_name"]} {pm["institution"]}")
        if c2.button("🗑️", key=f"del_pm_{pm["payment_method_id"]}"):
            delete_item("payment_methods", pm["payment_method_id"])