"""
Share inputs that fill each other in: change one person's % and the other
person's becomes the rest, so a split is one edit instead of two.
"""


def fill_rest(values: dict, changed, total: float = 100) -> dict:
    """
    The shares after `changed` was edited: the one other person takes
    `total` minus the new value (never below 0). With more people, the one
    other person who still has a share (0 = not in the household, as in
    Settings); if there's no single such person, nothing else changes.
    """
    others = [key for key in values if key != changed]
    if len(others) != 1:
        others = [key for key in others if values[key]]
    if len(others) != 1:
        return dict(values)
    rest = max(total - values[changed], 0)
    return {**values, others[0]: type(values[changed])(rest)}


def fill_rest_in_state(state, keys: dict, changed) -> None:
    """A widget on_change callback: applies fill_rest to the inputs whose session-state keys are `keys` (person → key)."""
    filled = fill_rest({person: state[key] for person, key in keys.items()}, changed)
    for person, key in keys.items():
        state[key] = filled[person]
