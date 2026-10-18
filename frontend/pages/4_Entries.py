"""
Entries: every expense you can see (yours, plus the shared ones), to audit
what was logged and fix it. Filter the table, tick a row, and the same form
as Add expense opens under it with that expense filled in: Save changes
edits it (PATCH, which leaves a trace of who changed it and when), or
delete it. Shaping lives in entries.py, the form in sections/entry_form.py.
"""
import datetime

import requests
import streamlit as st

import entries
import ui
from analytics_shaping import month_label
from common import SAO_PAULO, auth_headers, check, get_data, md, require_login, saved, show_toast
from config import API_BASE_URL
from money import format_brl
from sections import entry_form

ui.setup("Entries")
token = require_login()
show_toast()

def clear_selection() -> None:
    st.session_state["entries_table_nonce"] = st.session_state.get("entries_table_nonce", 0) + 1


ui.page_header("Entries", "Every expense you can see: check what was logged, fix a mistake, or delete it.")

expenses = get_data("expenditures", token) or []
if not expenses:
    st.info("Nothing logged yet.")
    st.page_link("pages/1_Add_expense.py", label="Add your first expense", icon=":material/edit_note:")
    st.stop()

table = entries.entries_frame(expenses, SAO_PAULO)
by_id = {e["expenditure_id"]: e for e in expenses}

# --- Filters, right above the table they narrow ---
this_month = datetime.datetime.now(SAO_PAULO).strftime("%Y-%m")
months = sorted(set(table["month"]) | {this_month}, reverse=True)
c1, c2, c3 = st.columns([1, 1, 1])
month = c1.selectbox("Month", [None, *months], index=1, key="entries_month",
                     format_func=lambda m: "All months" if m is None else month_label(m))
kind = c2.selectbox("Show", list(entries.KINDS), format_func=entries.KINDS.get, key="entries_kind")
people = sorted(table["logged_by"].unique())
logged_by = c3.selectbox("Logged by", [None, *people], key="entries_logged_by",
                         format_func=lambda p: "Anyone" if p is None else p)
c4, c5 = st.columns([1, 1])
categories = c4.multiselect("Categories", sorted(table["primary"].unique()), key="entries_categories",
                            placeholder="All categories")
search = c5.text_input("Search", key="entries_search", placeholder="e.g. groceries, Nubank, 45,90")

shown = entries.filter_entries(table, month, kind, logged_by, categories, search)

with ui.card("entries"):
    st.subheader("What was logged?")
    if shown.empty:
        st.caption("Nothing matches these filters.")
        st.stop()
    st.caption(md(entries.summary(shown) + ". Tick a row to fix or delete it."))
    # A save or delete bumps the key, so no row stays ticked once the table has changed under it.
    event = st.dataframe(shown[entries.TABLE_COLUMNS], hide_index=True, width="stretch",
                         column_config={"Price": st.column_config.TextColumn(help="The full amount"),
                                        "Your part": st.column_config.TextColumn(help="What you bear of it")},
                         on_select="rerun", selection_mode="single-row",
                         key=f"entries_table_{st.session_state.get('entries_table_nonce', 0)}")

picked_rows = (event or {}).get("selection", {}).get("rows", [])  # a dict in tests, an object live
if not picked_rows:
    st.stop()
expense = by_id[int(shown.iloc[picked_rows[0]]["id"])]
eid = expense["expenditure_id"]

# --- The picked expense: its trace, the form to fix it, and delete ---
with ui.card("edit"):
    st.subheader(f"Fix {entries.what_text(expense)} · {format_brl(expense['price'])}")
    st.caption(entries.trace_text(expense, SAO_PAULO))
    data = entry_form.Lookups(token)
    # The form's key carries the expense, so picking another one starts afresh.
    entry_form.render(token, data, prefix=f"edit{eid}", expense=expense, submit_label="Save changes",
                      on_saved=clear_selection)

    with st.expander("Delete this expense"):
        st.write("It goes for good, with its split" + (" (for both of you)." if expense.get("is_shared") else "."))
        if st.button("Delete it", key=f"delete_{eid}"):
            try:
                res = check(requests.delete(f"{API_BASE_URL}/expenditures/{eid}", headers=auth_headers(token)))
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")
            else:
                if res.status_code == 200:
                    clear_selection()
                    saved(f"Deleted: {entries.what_text(expense)} · {format_brl(expense['price'])}")
                else:
                    st.error(f"Error: {res.status_code} – {res.text}")
