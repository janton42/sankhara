"""Rules for planning a day's actions within a fixed hour budget."""

from sankhara.constants.config import ACTIONS

DAY_HOURS = 24


def hours_used(selected):
    """Total hours of the actions picked so far (empty slots are None)."""
    return sum(a["hours"] for a in selected if a)


def available_actions(selected, slot, actions=ACTIONS):
    """Actions that may go in `slot` given the picks in the other slots.

    The slot's own current pick is ignored, so it can always be swapped for
    anything that fits in the hours the other slots leave free.
    """
    others = [a for i, a in enumerate(selected) if a and i != slot]
    remaining = DAY_HOURS - hours_used(others)
    used_ids = {a["id"] for a in others}
    return [
        a
        for a in actions
        if a["hours"] <= remaining and (a["repeatable"] or a["id"] not in used_ids)
    ]
