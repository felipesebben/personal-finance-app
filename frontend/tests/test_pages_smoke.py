"""Every page renders without crashing when nobody is logged in (no API needed)."""
import pytest
from streamlit.testing.v1 import AppTest


def test_home_shows_the_login_form():
    at = AppTest.from_file("Home.py", default_timeout=30).run()
    assert not at.exception
    assert any(b.label == "Log In" for b in at.button)


@pytest.mark.parametrize("page", [
    "pages/1_Add_expense.py", "pages/2_Our_expenses.py", "pages/3_My_expenses.py",
    "pages/4_Entries.py", "pages/6_Settings.py",
])
def test_pages_ask_for_login(page):
    at = AppTest.from_file(page, default_timeout=30).run()
    assert not at.exception
