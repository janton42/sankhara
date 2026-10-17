import random

from sankhara.sim import tendencies as t


def test_affinity_and_cost():
    tend = {"generous": 1.0, "harsh": -1.0}
    assert t.affinity(tend, ("generous",)) == 1.0
    assert t.affinity(tend, ("generous", "harsh")) == 0.0
    assert t.affinity(tend, ()) == 0.0
    assert t.cost_multiplier(tend, ("generous",)) < 1 < t.cost_multiplier(tend, ("harsh",))


def test_strengthen_and_weaken_are_constant_steps_and_clamped():
    tend = {}
    t.strengthen(tend, ("diligent",))
    assert tend["diligent"] == t.SHIFT_STEP
    t.weaken(tend, ("diligent",))
    assert abs(tend["diligent"] - (t.SHIFT_STEP - t.DECLINE_STEP)) < 1e-9
    for _ in range(100):
        t.strengthen(tend, ("diligent",))
    assert tend["diligent"] == 1.0


def test_pull_toward_moves_part_way():
    child = {tag: 0.0 for tag in t.TAGS}
    parent = {tag: 0.0 for tag in t.TAGS} | {"harsh": 1.0}
    t.pull_toward(child, parent, 0.25)
    assert child["harsh"] == 0.25


def test_carry_keeps_pattern_and_karma_tilts_it():
    tend = {tag: 0.0 for tag in t.TAGS} | {"studious": 0.5}
    neutral = t.carry_into_next_life(tend, 0.0)
    assert neutral["studious"] == t.CARRY * 0.5
    good = t.carry_into_next_life(tend, 1.0)
    bad = t.carry_into_next_life(tend, -1.0)
    assert good["caring"] > 0 > bad["caring"]
    assert good["harsh"] < 0 < bad["harsh"]


def test_random_tendencies_cover_all_tags():
    tend = t.random_tendencies(random.Random(1))
    assert set(tend) == set(t.TAGS)
