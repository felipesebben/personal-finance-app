import streamlit as st
import requests

st.set_page_config(page_title="Manage Settings", page_icon="⚙️", layout="wide")

API_BASE_URL = "http://localhost:8000"

def send_post_request(enpoint: str, payload: dict, success_message: str):
    """
    Generic helper to send POST requests
    """
    try:
        response = requests.post(f"{API_BASE_URL}/{enpoint}/", json=payload)
        if response.status_code == 200:
            st.success(success_message)
            # Clear the cache so that the main page re-fetches the new data next time
            st.cache_data.clear()
        else:
            st.error(f"Error: {response.status_code}: – {response.text}")
    except requests.exceptions.ConnectionError:
        st.error("Connection Error: Could not connect to the API.")


st.title("⚙️ Manage Settings")
st.info("Use this page to add new people, categories, or payment methods, to your system.")

col1, col2, col3 = st.columns(3)

# Add Person
with col1:
    st.subheader("Add Person")
    with st.form("add_person", clear_on_submit=True):
        new_person = st.text_input("Name")
        submit_person = st.form_submit_button("Add Person")

        if submit_person and new_person:
            send_post_request("people", {"person_name": new_person}, f"Added {new_person}!")

# Add Category
with col2:
    st.subheader("Add Category")
    with st.form("add_category", clear_on_submit=True):
        new_primary = st.text_input("Primary Category")
        new_sub = st.text_input("Sub Category")
        submit_cat = st.form_submit_button("Add Category")

        if submit_cat and new_sub and new_primary:
            payload = {
                "primary_category": new_primary,
                "sub_category": new_sub,
                "cost_type": "Variable",
                "nature": "Normal"
            }
            send_post_request("categories", payload, f"Added {new_primary} – {new_sub}!")

with col3:
    st.subheader("Payment Method")
    with st.form("add_method", clear_on_submit=True):
        new_method = st.text_input("Method Name")
        new_inst = st.text_input("Institution (Bank)")
        submit_method = st.form_submit_button("Add Method")

        if submit_method and new_method:
            payload = {
                "method_name": new_method,
                "institution": new_inst,
            }
            send_post_request("payment_methods", payload, f"Added {new_method} – {new_inst}!")   