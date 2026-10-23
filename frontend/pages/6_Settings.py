import datetime

import pandas as pd
import requests
import streamlit as st

from analytics_shaping import month_label, shift_month
from common import SAO_PAULO, end_session, get_data as common_get, require_login
from config import API_BASE_URL
import settings_logic as logic
import ui

ui.setup("Settings")

token = require_login()
auth_headers = {"Authorization": f"Bearer {token}"}
me = (st.session_state.get("user_email") or "").lower()

# A message shown right before st.rerun() would never appear, so it waits
# here for the next run.
if "settings_toast" in st.session_state:
    st.toast(st.session_state.pop("settings_toast"), icon="✅")


# --- Helper Functions ---

def get_data(endpoint: str, token: str) -> list:
    """GET /<endpoint>/ with the session's token; an empty list on any failure."""
    return common_get(f"{endpoint}/", token)


def call(method: str, path: str, payload=None) -> str | None:
    """Sends one request; returns None on success, else a readable error."""
    try:
        response = requests.request(method, f"{API_BASE_URL}/{path}", json=payload, headers=auth_headers)
    except requests.exceptions.RequestException:
        return "Could not connect to the API."
    if response.status_code == 200:
        return None
    if response.status_code == 401:
        end_session()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    return detail if isinstance(detail, str) else f"Error {response.status_code}: {detail}"


def done(message: str) -> None:
    """After a successful change: fresh data, fresh editors, a toast."""
    st.session_state["settings_toast"] = message
    st.session_state["settings_nonce"] = st.session_state.get("settings_nonce", 0) + 1
    st.cache_data.clear()
    st.rerun()


nonce = st.session_state.get("settings_nonce", 0)


def editable_table(title: str, endpoint: str, rows: list, table: logic.Table, columns: dict, how: str) -> None:
    """
    One dimension as an editable table: edit cells, add a row at the bottom,
    select rows and press Delete. Nothing is written until Save, which first
    lists exactly what will change.
    """
    st.subheader(title)
    ui.lede(*how)
    df = pd.DataFrame(rows, columns=[table.key, *table.fields, "expense_count"])
    # Pin the column types: an empty list (no pets yet) or a missing field
    # leaves untyped columns, which the editor's checkbox/number columns reject.
    for flag in table.flags:
        df[flag] = df[flag].eq(True)
    df["expense_count"] = pd.to_numeric(df["expense_count"]).fillna(0).astype(int)
    df = df.sort_values(list(table.fields[:2]), key=lambda s: s.fillna("").str.lower()).reset_index(drop=True)

    edited = st.data_editor(
        df,
        key=f"{endpoint}_editor_{nonce}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_order=[*table.fields, "expense_count"],
        column_config={
            table.key: None,
            **columns,
            "expense_count": st.column_config.NumberColumn(
                "Used by", disabled=True, format="%d", help="How many expenses use it. Rows in use can't be removed.",
            ),
        },
    )

    plan = logic.plan_changes(rows, edited.to_dict("records"), table)
    if plan.empty and not plan.errors:
        return
    with st.container(border=True):
        for line in plan.lines:
            st.markdown(f"- {line}")
        for error in plan.errors:
            st.warning(error, icon=":material/warning:")
        save, discard = st.columns([1, 1])
        if save.button("Save changes", type="primary", key=f"{endpoint}_save_{nonce}",
                       disabled=bool(plan.errors) or plan.empty, width="stretch"):
            apply(endpoint, plan)
        if discard.button("Discard", key=f"{endpoint}_discard_{nonce}", width="stretch"):
            done("Changes discarded.")


def apply(endpoint: str, plan: logic.Plan) -> None:
    """Deletes, then edits, then adds, so a rename can free up a name an add reuses."""
    failures = []
    for row_id in plan.deletes:
        if err := call("DELETE", f"{endpoint}/{row_id}"):
            failures.append(err)
    for row_id, changes in plan.updates:
        if err := call("PATCH", f"{endpoint}/{row_id}", changes):
            failures.append(err)
    for payload in plan.adds:
        if err := call("POST", f"{endpoint}/", payload):
            failures.append(err)
    if failures:
        st.cache_data.clear()
        for err in failures:
            st.error(err)
        st.info("The other changes were saved. Reload the page to see the current list.")
        return
    count = len(plan.lines)
    done(f"Saved {count} change{'s' if count != 1 else ''}.")


# --- Main UI ---

ui.page_header("Settings", "Who shares expenses and how, and the lists Add expense offers.")

users = get_data("users", token)
household = get_data("household_settings", token)
categories = get_data("categories", token)
payment_methods = get_data("payment_methods", token)
pets = get_data("pets", token)

# --- Household ---
st.subheader("Household")
ui.lede(
    "Who shares expenses, and in what proportion.",
    " Set each person's share from your incomes, e.g. 60/40. It applies to expenses saved from now on; "
    "earlier ones keep the split they were saved with. Leave someone at 0% to keep them out.",
)

current = {s["user_id"]: float(s["share_pct"]) * 100 for s in household}
people = sorted(users, key=lambda u: (u["email"].lower() != me, u["full_name"] or ""))
shares = {}
for person in people:
    name, email = person["full_name"] or person["email"], person["email"]
    you = " (you)" if email.lower() == me else ""
    c_name, c_share = st.columns([3, 1])
    c_name.markdown(f"**{name}**{you}  \n{email}")
    shares[person["user_id"]] = c_share.number_input(
        "Share (%)", min_value=0.0, max_value=100.0, step=1.0,
        value=current.get(person["user_id"], 0.0),
        key=f"share_{person['user_id']}_{nonce}",
    )

if len(people) < 2:
    st.caption(
        "Adding your partner: they open this app's login page and choose **Sign up** with their email. "
        "Once they have, they appear here and you can give them a share."
    )

payload, problem = logic.household_payload(shares)
changed = {s["user_id"]: s["share_pct"] for s in payload} != {
    s["user_id"]: round(float(s["share_pct"]), 4) for s in household
}
if problem:
    st.caption(f"⚠️ {problem}")
if st.button("Save split", type="primary", disabled=bool(problem) or not changed, key=f"save_split_{nonce}"):
    if err := call("PUT", "household_settings/", {"settings": payload}):
        st.error(err)
    else:
        done("Household split saved.")

st.divider()

# --- Categories ---
editable_table(
    "Categories", "categories", categories, logic.CATEGORIES,
    {
        "primary_category": st.column_config.TextColumn("Category", required=True),
        "sub_category": st.column_config.TextColumn("Sub-category", required=True),
        "cost_type": st.column_config.SelectboxColumn(
            "Cost type", options=["Variable", "Fixed"], required=True, default="Variable",
            help="Fixed costs repeat every month (rent, internet); variable ones don't.",
        ),
        "for_pets": st.column_config.CheckboxColumn(
            "Pets", default=False, help="Tick for pet costs (food, vet…): Add expense then asks which pet it was for.",
        ),
    },
    ("Edit right in the table.", " Click a cell to rename it, type in the empty last row to add one, "
     "or select a row (the box on its left) and press Delete to remove it. Renaming also relabels past expenses."),
)

st.divider()

# --- Monthly targets ---
st.subheader("Monthly targets")
ui.lede("What you mean to spend a month, per category.",
        " Our expenses draws it as a dark tick on each category's bar, next to last month's grey one. "
        "For shared spending, at full price. Leave a category blank for no target.")
# A starting point from history: the last full months before this one.
last_month = shift_month(datetime.datetime.now(SAO_PAULO).strftime("%Y-%m"), -1)
history = common_get(f"analytics/shared?month={last_month}&months=12", token, default=None)
suggested, averaged = logic.suggest_targets(history if isinstance(history, dict) else None)
target_table = logic.target_rows(categories, get_data("category_targets", token), suggested,
                                 fill_blanks=st.session_state.get("targets_fill_blanks", False))
if target_table.empty:
    st.caption("Add a category first.")
else:
    if averaged:
        span = month_label(averaged[0]) + (f" to {month_label(averaged[-1])}" if len(averaged) > 1 else "")
        st.caption(f"Suggested: the average of {span}, rounded up to R$ 50. A starting point; change it freely.")
        if st.button("Fill blank targets with the suggestions", key=f"fill_targets_{nonce}"):
            st.session_state["targets_fill_blanks"] = True
            st.session_state["settings_nonce"] = nonce + 1  # a fresh table, filled in
            st.rerun()
    edited_targets = st.data_editor(
        target_table, hide_index=True, width="stretch", num_rows="fixed", key=f"targets_{nonce}",
        column_config={"Category": st.column_config.TextColumn(disabled=True),
                       "Target": st.column_config.TextColumn("Target (R$ a month)", help="e.g. 3.000,00"),
                       "Suggested": st.column_config.TextColumn(disabled=True,
                                                                help="From the last full months logged")},
    )
    if st.button("Save targets", key=f"save_targets_{nonce}"):
        targets, problems = logic.targets_payload(edited_targets)
        if problems:
            st.error("Not saved: " + " ".join(problems))
        else:
            error = call("PUT", "category_targets/", {"targets": targets})
            if error:
                st.error(error)
            else:
                st.session_state.pop("targets_fill_blanks", None)
                done(f"Targets saved: {len(targets)} categor{'y' if len(targets) == 1 else 'ies'}.")

st.divider()

# --- Payment methods ---
editable_table(
    "Payment methods", "payment_methods", payment_methods, logic.PAYMENT_METHODS,
    {
        "method_name": st.column_config.TextColumn("Method", required=True, help="e.g. Pix, Debit Card, Credit Card, Cash"),
        "institution": st.column_config.TextColumn("Bank / account", help="e.g. Nubank. Leave blank for Cash."),
        "is_credit": st.column_config.CheckboxColumn("Credit", default=False, help="Credit cards offer installments when you add an expense."),
        "is_joint": st.column_config.CheckboxColumn(
            "Joint", default=False,
            help="An account you both top up in advance, e.g. a shared card for groceries. "
                 "What it pays for never makes either of you owe the other.",
        ),
    },
    ("One row per way you pay, e.g. Pix · Nubank.", " Add expense asks for the bank whenever a method has one. "
     "Tick Credit for credit cards so it offers installments, and Joint for an account you both fund "
     "(name it apart from a personal card at the same bank, e.g. Nubank Conjunta)."),
)

st.divider()

# --- Pets ---
editable_table(
    "Pets", "pets", pets, logic.PETS,
    {"name": st.column_config.TextColumn("Name", required=True)},
    ("Who the pet expenses are for.", " For a category ticked Pets above, Add expense asks which pet it was, "
     "or Both for one expense shared by all of them, so Tableau can show what each one costs."),
)

st.divider()

# --- ETL Trigger ---
st.subheader("Publish to Tableau")
st.caption("Sends the latest data to the Tableau dashboard. Only needed when you want Tableau up to date; the app's own pages are always live.")

if st.button("Run ETL Pipeline"):
    with st.spinner("Pipeline running... (This may take a moment)"):
        try:
            response = requests.post(f"{API_BASE_URL}/refresh", headers=auth_headers)
            if response.status_code == 200:
                st.success("ETL Finished Successfully!")
                st.json(response.json())
            elif response.status_code == 401:
                end_session()
            else:
                st.error(f"Server Error: ({response.status_code})")
                st.code(response.text)
        except requests.exceptions.ConnectionError:
            st.error("Connection Failed")
            st.warning(f"Could not reach the backend at `{API_BASE_URL}`. Is the Docker container running?")

# --- Your account ---
st.divider()
mine = next((u for u in users if u["email"].lower() == me), None)
if mine:
    with st.expander("Delete my account"):
        st.caption("Only possible while no expenses or settlements are recorded under your name.")
        if st.button("Delete my account", key=f"delete_me_{nonce}"):
            if err := call("DELETE", f"users/{mine['user_id']}"):
                st.error(err)
            else:
                st.session_state.clear()
                st.rerun()
