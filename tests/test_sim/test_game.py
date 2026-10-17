import json

from sankhara.sim import game, save, tendencies
from sankhara.sim.state import EventInstance, GameState
from sankhara.sim.stations import ACTION_SLOTS, ADULT_AGE


def test_new_game_starts_as_young_ruler(state):
    player = state.player
    assert player.station == "ruler"
    assert player.age(state.year) == 20
    assert state.nation.ruler_id == player.id
    assert state.nation.dynasty == player.family_name
    assert len(state.nation.territory) == 19
    assert 2 <= len(state.settlements) <= 5
    assert sum(1 for s in state.settlements.values() if s.is_capital) == 1
    assert sum(1 for c in state.living() if c.is_advisor) == 3
    assert len(state.plan) == ACTION_SLOTS


def test_obligations_are_listed_first(state):
    state.events = [EventInstance("stranger", "A stranger", obligation="shelter", penalty=0.05)]
    opts = game.options(state)
    assert opts[0].obligation and opts[0].key == "event:0"
    assert all(not o.obligation for o in opts[1:])


def test_choose_rejects_duplicates_and_unaffordable(state):
    state.plan = [None] * ACTION_SLOTS
    assert game.choose(state, 0, "hold_court")
    assert not game.choose(state, 1, "hold_court")
    state.nation.treasury.coin = 0
    assert not game.choose(state, 1, "school")
    assert game.choose(state, 0, None)
    assert state.plan[0] is None


def test_costs_are_cumulative_across_slots(state):
    state.plan = [None] * ACTION_SLOTS
    state.nation.treasury.coin = 30
    state.player.tendencies = {}
    assert game.choose(state, 0, "hold_court")  # 20 coin
    assert not game.choose(state, 1, "hold_court")
    assert not game.choose(state, 1, "display")  # 50 coin, only 10 left


def test_habit_prefills_slots(state):
    state.player.tendencies = {t: -0.5 for t in tendencies.TAGS}
    state.player.tendencies["generous"] = 1.0
    game.begin_year(state)
    assert "lower_taxes" in state.defaults
    assert state.plan[: len(state.defaults)] == state.defaults
    state.player.tendencies = {t: 0.0 for t in tendencies.TAGS}
    game.begin_year(state)
    assert state.defaults == []


def test_choosing_strengthens_and_overriding_habit_weakens(state):
    player = state.player
    player.tendencies = {t: 0.0 for t in tendencies.TAGS}
    state.events = []
    state.plan = ["hold_court", None, None]
    state.defaults = ["lower_taxes"]
    game.end_year(state)
    assert player.tendencies["caring"] > 0
    assert player.tendencies["generous"] < 0


def test_skipping_an_obligation_costs_karma(state):
    def year(take):
        s = game.new_game(seed=99)
        s.events = [EventInstance("stranger", "x", obligation="shelter", penalty=0.05)]
        s.plan = ["event:0" if take else None, None, None]
        s.defaults = []
        before = s.soul.karma
        game.end_year(s)
        return s.soul.karma - before

    assert year(take=True) > 0 > year(take=False)


def test_karma_is_never_shown_in_option_text(state):
    for opt in game.options(state):
        text = f"{opt.action.name} {opt.action.text} {opt.blurb}".lower()
        assert "karma" not in text and "rebirth" not in text


def test_life_ends_and_next_begins_in_same_nation(state):
    nation_name = state.nation.name
    old = state.player
    old.death_age = old.age(state.year)
    report = game.end_year(state)
    assert report.life_ended and not old.alive
    assert state.soul.lives[-1]["name"] == old.full_name
    assert state.nation.ruler_id != old.id  # someone succeeded
    lines = game.begin_next_life(state)
    new = state.player
    assert new.id != old.id and new.alive and new.is_player and not old.is_player
    assert new.age(state.year) == ADULT_AGE
    assert state.nation.name == nation_name
    assert lines and "born" in lines[0]


def test_rebirth_station_is_random():
    stations = set()
    for seed in range(25):
        s = game.new_game(seed=seed)
        s.player.death_age = s.player.age(s.year)
        game.end_year(s)
        game.begin_next_life(s)
        stations.add(s.player.station)
    assert len(stations) >= 3


def test_karma_shapes_conditions_of_next_life():
    def born_with(karma, seed):
        s = game.new_game(seed=seed)
        s.player.death_age = s.player.age(s.year)
        game.end_year(s)
        s.soul.karma = karma
        game.begin_next_life(s)
        return s.player

    good = [born_with(1.0, seed) for seed in range(12)]
    bad = [born_with(-1.0, seed) for seed in range(12)]
    assert sum(p.fortune for p in good) > sum(p.fortune for p in bad)
    assert sum(p.family_stability for p in good) < sum(p.family_stability for p in bad)
    wholesome = sum(p.tendencies["caring"] - p.tendencies["harsh"] for p in good)
    unwholesome = sum(p.tendencies["caring"] - p.tendencies["harsh"] for p in bad)
    assert wholesome > unwholesome


def test_heir_succeeds_dead_ruler(state):
    player = state.player
    player.death_age = player.age(state.year)
    heir = None
    # give the ruler a child so there is an heir
    from sankhara.sim.people import create_character, create_spouse

    spouse = create_spouse(state, player)
    mother, father = (spouse, player) if player.gender == "male" else (player, spouse)
    heir = create_character(
        state, "noble", player.settlement_id, state.year - 1, mother=mother, father=father
    )
    game.end_year(state)
    assert state.nation.ruler_id == heir.id
    assert heir.station == "ruler"


def test_save_and_load_round_trip(tmp_path, state, play):
    play(state, 5)
    path = tmp_path / "save.json"
    save.save(state, path)
    loaded = save.load(path)
    assert json.dumps(loaded.to_dict(), sort_keys=True) == json.dumps(
        state.to_dict(), sort_keys=True
    )
    # the RNG is restored too, so both copies play on identically
    play(state, 3, seed=5)
    play(loaded, 3, seed=5)
    assert json.dumps(loaded.to_dict(), sort_keys=True) == json.dumps(
        state.to_dict(), sort_keys=True
    )


def test_from_dict_ignores_unknown_keys(state):
    data = state.to_dict()
    data["something_new"] = 1
    assert GameState.from_dict(data).year == state.year


def test_long_game_stays_sane(play):
    s = play(game.new_game(seed=3), 200, seed=3)
    assert len(s.soul.lives) >= 3
    assert 500 < s.total_population() < 30000
    assert 0 <= s.nation.stability <= 100 and 0 <= s.nation.learning <= 100
    assert len(s.characters) < 600
    assert s.player.alive
