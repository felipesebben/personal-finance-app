import streamlit as st
import requests

from config import API_BASE_URL
import ui

ui.setup("Home")

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
    url = f"{API_BASE_URL}/token"
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
    url = f"{API_BASE_URL}/users/"
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
    
PASSWORD_MIN_LENGTH = 8


def request_password_reset(email):
    """
    Asks the API to email a reset link. The API answers the same way whether
    or not the account exists, so this only reports connection failures.

    :return: `True` if the request reached the API, `False` otherwise.
    :rtype: bool
    """
    try:
        response = requests.post(f"{API_BASE_URL}/password-reset/request", json={"email": email})
        if response.status_code == 202:
            return True
        st.error(f"Could not request a reset: {response.status_code}")
        return False
    except requests.exceptions.ConnectionError:
        st.error("Connection Error: Is the backend running?")
        return False


def confirm_password_reset(reset_token, new_password):
    """
    Redeems a reset link with the new password.

    :return: `None` on success, otherwise the error message to show.
    :rtype: str | None
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/password-reset/confirm",
            json={"token": reset_token, "new_password": new_password},
        )
    except requests.exceptions.ConnectionError:
        return "Connection Error: Is the backend running?"
    if response.status_code == 200:
        return None
    if response.status_code == 400:
        return response.json().get("detail", "This reset link is invalid or has expired.")
    return f"Could not reset the password: {response.status_code}"


def logout_user():
    """
    Clears the session state, effectively running the user out.
    """
    st.session_state.clear()
    st.rerun()

# --- 3. Main UI Logic  ---
# Arriving from a reset email: http://<host>:8501/?reset_token=...
reset_token = st.query_params.get("reset_token")
if reset_token:
    ui.page_header("Set a new password", "Choose a new password for your account. The link works once.")
    with st.form("reset_password_form"):
        new_password = st.text_input("New password", type="password", help=f"At least {PASSWORD_MIN_LENGTH} characters.")
        repeat_password = st.text_input("Repeat new password", type="password")
        submit_reset = st.form_submit_button("Set Password")

        if submit_reset:
            if len(new_password) < PASSWORD_MIN_LENGTH:
                st.warning(f"The password must be at least {PASSWORD_MIN_LENGTH} characters.")
            elif new_password != repeat_password:
                st.warning("The passwords don't match.")
            else:
                error = confirm_password_reset(reset_token, new_password)
                if error:
                    st.error(error)
                else:
                    # Drop the spent token from the URL and show the login form.
                    st.query_params.clear()
                    st.session_state["password_reset_done"] = True
                    st.rerun()
    if st.button("Back to log in"):
        st.query_params.clear()
        st.rerun()
    st.stop()

# Case A: User is not logged in (Show Login/Register Forms)
if st.session_state["access_token"] is None:
    ui.page_header(ui.APP_NAME, "Your household's shared spending, split fairly by income. Log in, or create an account if you're new.")
    if st.session_state.pop("password_reset_done", False):
        st.success("Password updated. You can now log in with the new one.")

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

        with st.expander("Forgot password?"):
            with st.form("forgot_password_form", clear_on_submit=True):
                reset_email = st.text_input("Your account's email")
                submit_forgot = st.form_submit_button("Email me a reset link")

                if submit_forgot:
                    if not reset_email:
                        st.warning("Please enter your email.")
                    elif request_password_reset(reset_email):
                        st.success("If that account exists, we've sent a reset link.")
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

    ui.page_header(ui.APP_NAME, "What would you like to do?")

    cards = [
        ("Add expense", "Record a purchase in a few taps.", "pages/1_Add_expense.py", ":material/edit_note:"),
        ("Our expenses", "How our shared spending is doing: this month against earlier ones, "
                         "the joint account, and who owes whom.", "pages/2_Our_expenses.py", ":material/home:"),
        ("My expenses", "How your own spending is doing: your part of what you share, plus what's only yours.",
         "pages/3_My_expenses.py", ":material/person:"),
        ("Settings", "Categories, payment methods, pets, and the household split between you.",
         "pages/5_Settings.py", ":material/settings:"),
    ]
    for col, (title, text, page, icon) in zip(st.columns(len(cards)), cards):
        with col:
            with st.container(border=True):
                st.subheader(title)
                st.write(text)
                st.page_link(page, label=f"Open {title}", icon=icon)

    st.write("")
    if st.button("Log Out", key="main_logout"):
        logout_user()
