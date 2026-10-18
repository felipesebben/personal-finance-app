"""
Add expense: one purchase at a time. The form itself is sections/entry_form
(shared with Entries, which edits what's logged here).
"""
from decimal import Decimal

import streamlit as st

from common import SAO_PAULO, get_data, md, require_login, show_toast
import entry_checks
from sections import entry_form
import ui

ui.setup("Add expense")
token = require_login()
show_toast()

data = entry_form.Lookups(token)
household_data = data.household
my_user_id = data.my_user_id


@st.fragment
def expense_entry_form():
    """
    A fragment, so typing in the form reruns only this function rather
    than the whole page, while the cascading selects, the credit-only
    installments and the price preview stay live (st.form would freeze them
    until submit).
    """
    entry_form.render(token, data)


# -- Main Page UI --
ui.page_header("Add expense", "Record one purchase. See how it's going on Our expenses and My expenses.")


def ratio_text() -> str:
    """'Felipe 60% · Lívia 40%', from the household split, or '' if none is set."""
    parts = [
        f"{m['user'].get('full_name') or m['user']['email']} {Decimal(str(m['share_pct'])) * 100:.0f}%"
        for m in household_data or []
    ]
    return " · ".join(parts)


ratio = ratio_text()
ui.lede(
    "Record one purchase.",
    (f" Shared expenses are split between you by the household ratio ({ratio}); " if ratio
     else " Shared expenses are split between you by the household ratio; ")
    + "personal ones stay private to you.",
)
# Where logging has got to, to see where backfilling stopped.
for line in entry_checks.backfill_lines(get_data("expenditures", token), my_user_id, SAO_PAULO):
    st.caption(md(line))
if not data.ready:
    st.warning("Add at least one category and one payment method on the **Settings** page first.")
    st.page_link("pages/6_Settings.py", label="Open Settings", icon=":material/settings:")
else:
    if not household_data:
        st.info("No household split is set yet, so shared expenses can't be saved. Set it on the Settings page.")
    with st.expander("What does “shared” change?"):
        st.write(
            "A **shared** expense is visible to both of you, and each of you bears your share of it "
            "by the household ratio (or by a custom split you set for that one expense). "
            "Turn **Shared** off for something only you pay for: your partner won't see it."
        )
    expense_entry_form()
