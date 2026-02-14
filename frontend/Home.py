import streamlit as st
import requests
import os

# Define the API URL
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Personal Finance", page_icon="🫰", layout="wide")

# --- 1. Session State Initialization ---
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None

# --- 2. Helper Functions ---

def login_user(email, password):
    """
    Sends a POST request to the API to authenticate the user and retrieve a JWT token.
    
    :param email: The user's email address.
    :type email: str
    :param password: The plain-text password.
    :type password: str
    :return: A dictionary containing `access_token` if successful, or `None` if failed.
    :rtype: dict | None
    """
    url = f"{API_URL}/token"
    # OAuth2 expects form-data (username/password)
    payload = {"username": email, "password": password}

    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            return response.json()
        else:
            st.error("Invalid Email or Password")
            return None
    except requests.exceptions.ConnectionError:
        st.error("Connection Error: Is the backend running?")
        return None
    
def register_user(fullname, email, password):
    """
    Registers a new user in the database.
    
    :param fullname: The user's full name.
    :type fullname: str
    :param email: The user's email address.
    :type email: str
    :param password: The plain-text password.
    :type password: str
    :return: `True` if registration was successful, `False` otherwise.
    :rtype: bool
    """
    url = f"{API_URL}/users/"
    payload = {
        "full_name": fullname,
        "email": email,
        "password": password
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Registration failed: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Connection Error: is the backend running?")
        return False
    
def logout_user():
    """
    Clears the session state, effectively running the user out.
    """
    st.session_state.clear()
    st.rerun()

# --- 3. Main UI Logic  ---
# Case A: User is not logged in (Show Login/Register Forms)
if st.session_state["access_token"] is None:
    st.title("Secure Access")

    # Create two tabs: one for Login, one for Sign Up
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])

    # Tab 1: Login
    with tab1:
        with st.form("login_form"):
            email_input = st.text_input("Email")
            password_input = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Log In")

            if submit_login:
                if email_input and password_input:
                    token_data = login_user(email_input, password_input)
                    if token_data:
                        new_token = token_data["access_token"]

                        st.session_state.clear()

                        st.session_state["access_token"] = new_token
                        st.session_state["user_email"] = email_input

                        st.success("Login Successful!")
                        st.rerun()
                else:
                    st.warning("Please enter both email and password.")
    # Tab 2: Register
    with tab2:
        st.write("New here? Create an account.")
        with st.form("register_form"):
            new_name = st.text_input("Full Name")
            new_email = st.text_input("Email")
            new_pass = st.text_input("Password", type="password")
            submit_register = st.form_submit_button("Create Account")

            if submit_register:
                if new_name and new_email and new_pass:
                    success = register_user(new_name, new_email, new_pass)
                    if success:
                        st.success("Account created! You can now log in.")
                else:
                    st.warning("Please fill in all fields.")

# Case B: User is logged in (Show Welcome Screen)
else:
    with st.sidebar:
        st.write(f"Logged in as: **{st.session_state.get('user_email', 'User')}**")
        if st.button("Log Out", key="sidebar_logout"):
            logout_user()

    st.title("Finance Dashboard")
    st.info("Welcome! You are securely logged in.")

    st.write("### Where to go next?")
    st.write("**Check the Sidebar** to access the Tracker, the Analytics page or Settings.")

    st.write("---")
    if st.button("Log Out", key="main_logout"):
        logout_user()
