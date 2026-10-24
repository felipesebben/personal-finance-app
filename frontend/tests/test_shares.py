"""Share inputs that fill each other in (frontend/shares.py)."""
from shares import fill_rest, fill_rest_in_state


def test_two_people_the_other_takes_the_rest():
    assert fill_rest({1: 50, 2: 20}, 1) == {1: 50, 2: 50}
    assert fill_rest({1: 80.0, 2: 0.0}, 2) == {1: 100.0, 2: 0.0}


def test_never_below_zero_and_keeps_the_type():
    assert fill_rest({1: 100, 2: 5}, 1) == {1: 100, 2: 0}
    filled = fill_rest({1: 60.0, 2: 10.0}, 1)
    assert filled == {1: 60.0, 2: 40.0} and isinstance(filled[2], float)


def test_more_people_the_one_other_who_shares():
    # Settings lists every account; 0% means not in the household.
    assert fill_rest({1: 50.0, 2: 80.0, 3: 0.0}, 1) == {1: 50.0, 2: 50.0, 3: 0.0}


def test_no_single_other_person_changes_nothing():
    assert fill_rest({1: 50, 2: 30, 3: 20}, 1) == {1: 50, 2: 30, 3: 20}
    assert fill_rest({1: 70.0, 2: 0.0, 3: 0.0}, 1) == {1: 70.0, 2: 0.0, 3: 0.0}
    assert fill_rest({1: 40}, 1) == {1: 40}


def test_in_state_writes_back_through_the_keys():
    state = {"a": 30, "b": 80}
    fill_rest_in_state(state, {1: "a", 2: "b"}, 1)
    assert state == {"a": 30, "b": 70}
