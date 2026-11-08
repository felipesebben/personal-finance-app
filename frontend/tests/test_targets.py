"""targets: whole-category and sub-category targets as the views use them."""
import targets

ROWS = [{"primary_category": "Pets", "sub_category": None, "amount": "1500.00"},
        {"primary_category": "Pets", "sub_category": "Grooming", "amount": "200.00"},
        {"primary_category": "Food", "amount": "2400.00"},  # an older API: no sub_category at all
        "not a row"]


def test_whole_keeps_only_whole_categories():
    assert targets.whole(ROWS) == {"Pets": 1500.0, "Food": 2400.0}
    assert targets.whole(None) == {}


def test_subs_by_name_for_one_category_or_by_label_for_all():
    assert targets.subs(ROWS, "Pets") == {"Grooming": 200.0}
    assert targets.subs(ROWS, "Food") == {}
    assert targets.subs(ROWS) == {"Pets › Grooming": 200.0}


def test_labels_read_back():
    assert targets.label("Pets", "Grooming") == "Pets › Grooming" and targets.label("Pets") == "Pets"
    assert targets.split_label("Pets › Grooming") == ("Pets", "Grooming")
    assert targets.split_label("Pets") == ("Pets", None)
