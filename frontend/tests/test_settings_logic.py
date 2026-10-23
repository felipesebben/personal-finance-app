"""From an edited Settings table to the API calls that apply it."""
import math

import settings_logic as logic
from settings_logic import CATEGORIES, PAYMENT_METHODS, PETS, household_payload, plan_changes

CATS = [
    {"category_id": 1, "primary_category": "Food", "sub_category": "Groceries", "cost_type": "Variable", "expense_count": 3},
    {"category_id": 2, "primary_category": "Leisure", "sub_category": "Streaming", "cost_type": "Fixed", "expense_count": 0},
]


def edited(*changes, drop=(), add=()):
    """CATS as the editor returns them, with per-id field changes, rows removed and rows added."""
    rows = [dict(r) for r in CATS if r["category_id"] not in drop]
    for row_id, fields in changes:
        next(r for r in rows if r["category_id"] == row_id).update(fields)
    # Rows typed into the editor's last line come back with no id and NaN counts.
    return rows + [{"category_id": math.nan, "expense_count": math.nan, **a} for a in add]


def test_no_edits_is_an_empty_plan():
    plan = plan_changes(CATS, edited(), CATEGORIES)
    assert plan.empty and not plan.errors and not plan.lines


def test_a_rename_is_a_patch_of_only_the_changed_field():
    plan = plan_changes(CATS, edited((1, {"sub_category": "Supermarket "})), CATEGORIES)
    assert plan.updates == [(1, {"sub_category": "Supermarket"})]  # trimmed
    assert plan.lines == ["Rename Food › Groceries → Food › Supermarket"]


def test_changing_cost_type_reads_as_a_sentence():
    plan = plan_changes(CATS, edited((2, {"cost_type": "Variable"})), CATEGORIES)
    assert plan.updates == [(2, {"cost_type": "Variable"})]
    assert plan.lines == ["Leisure › Streaming: cost type → Variable"]


def test_a_new_row_is_a_post():
    plan = plan_changes(CATS, edited(add=[{"primary_category": "Pets", "sub_category": "Vet", "cost_type": "Variable"}]), CATEGORIES)
    assert plan.adds == [{"primary_category": "Pets", "sub_category": "Vet", "cost_type": "Variable", "for_pets": False}]
    assert plan.lines == ["Add Pets › Vet"]


def test_an_untouched_blank_row_is_ignored():
    plan = plan_changes(CATS, edited(add=[{"primary_category": None, "sub_category": "", "cost_type": None}]), CATEGORIES)
    assert plan.empty and not plan.errors


def test_a_half_filled_row_blocks_saving():
    plan = plan_changes(CATS, edited(add=[{"primary_category": "Pets", "sub_category": None, "cost_type": "Variable"}]), CATEGORIES)
    assert plan.adds == []
    assert plan.errors == ["Fill in every column for “Pets › …”."]


def test_removing_an_unused_row_is_a_delete():
    plan = plan_changes(CATS, edited(drop=[2]), CATEGORIES)
    assert plan.deletes == [2]
    assert plan.lines == ["Remove Leisure › Streaming"]


def test_removing_a_row_in_use_is_blocked_with_the_reason():
    plan = plan_changes(CATS, edited(drop=[1]), CATEGORIES)
    assert plan.deletes == []
    assert plan.errors == [
        "Food › Groceries can't be removed: 3 expenses use it. Rename it instead, or delete those expenses first."
    ]


def test_duplicates_are_caught_before_saving_case_insensitively():
    plan = plan_changes(CATS, edited(add=[{"primary_category": "food", "sub_category": "groceries", "cost_type": "Fixed"}]), CATEGORIES)
    assert plan.errors == ["food › groceries appears twice."]


def test_ids_that_came_back_as_floats_still_match():
    # A NaN in the id column (from an added row) turns the other ids into floats.
    rows = edited((1, {"sub_category": "Market"}), add=[{"primary_category": "Pets", "sub_category": "Vet", "cost_type": "Variable"}])
    for r in rows:
        r["category_id"] = float(r["category_id"])
    plan = plan_changes(CATS, rows, CATEGORIES)
    assert plan.updates == [(1, {"sub_category": "Market"})]
    assert plan.deletes == []


# --- payment methods -----------------------------------------------------

PMS = [
    {"payment_method_id": 5, "method_name": "Pix", "institution": None, "is_credit": False, "expense_count": 0},
]


def test_blank_institution_stays_none_and_credit_is_a_bool():
    rows = [dict(PMS[0], institution=""), {"payment_method_id": None, "method_name": "Credit Card",
                                           "institution": "Nubank", "is_credit": None, "expense_count": None}]
    plan = plan_changes(PMS, rows, PAYMENT_METHODS)
    assert plan.updates == []
    assert plan.adds == [{"method_name": "Credit Card", "institution": "Nubank", "is_credit": False, "is_joint": False}]
    assert plan.lines == ["Add Credit Card · Nubank"]


def test_adding_a_bank_and_ticking_credit():
    plan = plan_changes(PMS, [dict(PMS[0], institution="Nubank", is_credit=True)], PAYMENT_METHODS)
    assert plan.updates == [(5, {"institution": "Nubank", "is_credit": True})]
    assert plan.lines == ["Rename Pix → Pix · Nubank; Pix · Nubank: credit (offers installments)"]


def test_ticking_joint_on_a_payment_method():
    plan = plan_changes(PMS, [dict(PMS[0], is_joint=True)], PAYMENT_METHODS)
    assert plan.updates == [(5, {"is_joint": True})]
    assert plan.lines == ["Pix: a joint account (nobody owes for it)"]


def test_rows_from_an_api_without_is_joint_read_as_personal():
    # PMS has no is_joint key, as before this field existed: no change planned.
    assert plan_changes(PMS, [dict(PMS[0])], PAYMENT_METHODS).updates == []


def test_ticking_pets_on_a_category():
    plan = plan_changes(CATS, edited((2, {"for_pets": True})), CATEGORIES)
    assert plan.updates == [(2, {"for_pets": True})]
    assert plan.lines == ["Leisure › Streaming: asks which pet"]


# --- pets ------------------------------------------------------------------

def test_pets_add_rename_and_block_removing_one_in_use():
    pets = [{"pet_id": 1, "name": "Thor", "expense_count": 4}, {"pet_id": 2, "name": "Luna", "expense_count": 0}]
    rows = [dict(pets[1], name="Lua"), {"pet_id": None, "name": "Bob", "expense_count": None}]
    plan = plan_changes(pets, rows, PETS)
    assert plan.updates == [(2, {"name": "Lua"})]
    assert plan.adds == [{"name": "Bob"}]
    assert plan.errors == ["Thor can't be removed: 4 expenses use it. Rename it instead, or delete those expenses first."]


# --- household split -----------------------------------------------------

def test_household_payload_drops_zero_shares_and_converts_to_fractions():
    payload, problem = household_payload({12: 60.0, 13: 40.0, 14: 0.0})
    assert problem is None
    assert payload == [{"user_id": 12, "share_pct": 0.6}, {"user_id": 13, "share_pct": 0.4}]


def test_one_person_at_100_is_a_valid_household():
    assert household_payload({12: 100.0}) == ([{"user_id": 12, "share_pct": 1.0}], None)


def test_household_payload_explains_what_is_wrong():
    assert household_payload({12: 60.0, 13: 30.0})[1] == "Shares must add up to 100% (now 90%)."
    assert household_payload({12: 0.0})[1] == "Give at least one person a share."


# --- monthly targets --------------------------------------------------------

def test_target_rows_list_each_primary_category_once_with_its_target():
    categories = [{"primary_category": "Food", "sub_category": "Groceries"},
                  {"primary_category": "Food", "sub_category": "Delivery"},
                  {"primary_category": "pets", "sub_category": "Vet"}]
    rows = logic.target_rows(categories, [{"primary_category": "Food", "amount": "3000.00"}])
    assert list(rows["Category"]) == ["Food", "pets"]
    assert list(rows["Target"]) == ["3.000,00", ""]


def test_targets_payload_reads_brazilian_amounts_and_blocks_bad_ones():
    import pandas as pd
    ok, problems = logic.targets_payload(pd.DataFrame({"Category": ["Food", "Pets", "Home"],
                                                        "Target": ["3.000,00", "", None]}))
    assert ok == [{"primary_category": "Food", "amount": "3000.00"}] and problems == []
    _, problems = logic.targets_payload(pd.DataFrame({"Category": ["Food", "Pets"], "Target": ["abc", "0"]}))
    assert [p.split(":")[0] for p in problems] == ["Food", "Pets"]  # both blocked, each named


def test_suggested_targets_average_the_last_full_months_rounded_up():
    from conftest import sample_payload
    history = sample_payload("2026-09", is_partial=False, as_of_day=30)  # Jun–Sep 2026
    suggested, months = logic.suggest_targets(history)
    assert months == ["2026-07", "2026-08", "2026-09"]
    # Food: (600 + 900 + 370) / 3 = 623,33 -> R$ 650; Housing R$ 2.000 a month.
    assert suggested["Food"] == 650.0 and suggested["Housing"] == 2000.0
    # Logging began on 26 August: August doesn't count, only September does.
    late, months = logic.suggest_targets({**history, "first_date": "2026-08-26"})
    assert months == ["2026-09"] and late["Food"] == 400.0
    assert logic.suggest_targets(None) == ({}, [])


def test_blank_targets_fill_with_suggestions_only_when_asked():
    categories = [{"primary_category": "Food"}, {"primary_category": "Pets"}]
    targets = [{"primary_category": "Pets", "amount": "800.00"}]
    rows = logic.target_rows(categories, targets, {"Food": 650.0, "Pets": 900.0})
    assert list(rows["Target"]) == ["", "800,00"] and list(rows["Suggested"]) == ["R$ 650,00", "R$ 900,00"]
    filled = logic.target_rows(categories, targets, {"Food": 650.0, "Pets": 900.0}, fill_blanks=True)
    assert list(filled["Target"]) == ["650,00", "800,00"]  # a set target is never overwritten
    assert logic.targets_payload(filled)[0] == [{"primary_category": "Food", "amount": "650.00"},
                                               {"primary_category": "Pets", "amount": "800.00"}]
