from sankhara.constants.config import ACTIONS
from sankhara.core.day_plan import DAY_HOURS, available_actions, hours_used


def action(id_, hours, repeatable=True):
    return {"id": id_, "name": id_, "hours": hours, "repeatable": repeatable}


SLEEP = action("sleep", 8, repeatable=False)
WORK = action("work", 6)
NAP = action("nap", 2)
TEST_ACTIONS = [SLEEP, WORK, NAP]


def ids(actions):
    return [a["id"] for a in actions]


def test_hours_used_ignores_empty_slots():
    assert hours_used([None, SLEEP, None, WORK]) == 14
    assert hours_used([None, None]) == 0


def test_empty_day_allows_everything():
    assert ids(available_actions([None] * 4, 0, TEST_ACTIONS)) == ["sleep", "work", "nap"]


def test_non_repeatable_action_only_once():
    selected = [SLEEP, None, None, None]
    assert "sleep" not in ids(available_actions(selected, 1, TEST_ACTIONS))


def test_actions_must_fit_remaining_hours():
    selected = [SLEEP, WORK, None, None]  # 14h used, 10h left
    assert ids(available_actions(selected, 2, TEST_ACTIONS)) == ["work", "nap"]
    selected = [SLEEP, WORK, WORK, None]  # 20h used, 4h left
    assert ids(available_actions(selected, 3, TEST_ACTIONS)) == ["nap"]


def test_a_slot_can_swap_its_own_pick_in_a_full_day():
    selected = [SLEEP, WORK, WORK, NAP]  # exactly 22h
    # slot 0 holds sleep; swapping it should be allowed even though the day is near full
    assert "sleep" in ids(available_actions(selected, 0, TEST_ACTIONS))
    assert "work" in ids(available_actions(selected, 0, TEST_ACTIONS))


def test_real_actions_fit_in_a_day():
    assert all(a["hours"] <= DAY_HOURS for a in ACTIONS)
