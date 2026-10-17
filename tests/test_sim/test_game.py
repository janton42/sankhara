import json

from sankhara.sim import discoveries, game, save, tendencies
from sankhara.sim.state import EventInstance, GameState
from sankhara.sim.stations import ACTION_SLOTS, ADULT_AGE, rebirth_weights, station_title


def _quiet(state):
    """No events and nothing planned, so a test controls the year."""
    state.events = []
    state.plan = [None] * ACTION_SLOTS
    state.defaults = []


def test_new_game_starts_as_a_young_leader_of_a_small_band(state):
    player = state.player
    assert player.station == "leader"
    assert player.age(state.year) == 20
    assert state.nation.leader_id == player.id
    assert 100 < state.total_population() < 1500
    assert len(state.settlements) == 3
    assert all(s.kind == "camp" for s in state.settlements.values())
    assert set(state.nation.known) == set(discoveries.START_KNOWN)
    assert discoveries.stirring(state)
    assert len(state.neighbours) == 3 and not any(n.met for n in state.neighbours.values())
    assert sum(1 for c in state.living() if c.is_elder) == 4
    assert len(state.plan) == ACTION_SLOTS


def test_there_is_no_money_or_trade_goods_at_the_start(state):
    assert discoveries.categories(state.nation) == ["food", "hands", "regard"]
    text = json.dumps(state.to_dict()).lower()
    assert "coin" not in text and "goods" not in text


def test_obligations_are_listed_first(state):
    state.events = [EventInstance("stranger", "A stranger", obligation="welcome_stranger")]
    opts = game.options(state)
    assert opts[0].kind == "obligation" and opts[0].key == "event:0"
    assert all(o.kind != "obligation" for o in opts[1:])


def test_choose_rejects_duplicates_and_unaffordable(state):
    _quiet(state)
    assert game.choose(state, 0, "call_together")
    assert not game.choose(state, 1, "call_together")
    state.player.means.set("regard", 0)
    assert not game.choose(state, 0, "call_together")
    assert game.choose(state, 0, None)
    assert state.plan[0] is None


def test_costs_are_cumulative_across_slots(state):
    _quiet(state)
    state.player.tendencies = {}
    state.player.means.set("regard", 6)
    assert game.choose(state, 0, "call_together")  # 4 regard
    assert not game.choose(state, 1, "drive_out")  # 3 regard, only 2 left


def test_a_project_holds_its_slot_until_finished(state):
    _quiet(state)
    state.player.tendencies = {}
    assert game.choose(state, 1, "new:teach_young:")
    game.end_year(state)
    project = state.projects_of(state.player_id)[0]
    assert state.plan[1] == f"p:{project.id}"
    report = None
    for _ in range(10):
        state.events = []
        state.player.means.set("hands", 10)
        report = game.end_year(state)
        if str(project.id) not in state.projects:
            break
    assert str(project.id) not in state.projects
    assert any(i.startswith("Finished") for i in report.interrupts)


def test_setting_aside_the_peoples_work_passes_it_on(state):
    _quiet(state)
    game.choose(state, 0, "new:teach_young:")
    game.end_year(state)
    project = state.projects_of(state.player_id)[0]
    state.events = []
    state.plan = [None] * ACTION_SLOTS
    game.end_year(state)
    assert project.leader_id != state.player_id
    assert str(project.id) not in state.commitments


def test_setting_aside_your_own_undertaking_ends_it(state):
    _quiet(state)
    game.choose(state, 0, "new:hoard:")
    game.end_year(state)
    project = state.projects_of(state.player_id)[0]
    state.events = []
    state.plan = [None] * ACTION_SLOTS
    game.end_year(state)
    assert str(project.id) not in state.projects


def test_a_project_stalls_without_means(state):
    _quiet(state)
    game.choose(state, 0, "new:teach_young:")
    game.end_year(state)
    state.events = []
    state.player.means.set("hands", 0)
    report = game.end_year(state)
    assert any(i.startswith("Stalled") for i in report.interrupts)
    assert state.projects_of(state.player_id)[0].stalled


def test_an_idea_without_forms_is_simply_understood(state):
    _quiet(state)
    d = discoveries.DISCOVERIES["food_keeping"]
    state.nation.insight[d.id] = d.cost
    game.end_year(state)
    assert "food_keeping" in state.nation.known


def test_a_leader_chooses_the_shape_of_a_new_custom(state):
    _quiet(state)
    d = discoveries.DISCOVERIES["gifts"]
    state.nation.insight[d.id] = d.cost
    report = game.end_year(state)
    assert state.pending_choice == "gifts"
    assert any("choice" in i for i in report.interrupts)
    game.choose_form(state, "feasts")
    assert state.nation.known["gifts"] == "feasts"
    assert state.pending_choice is None


def test_working_at_an_idea_brings_it_closer(state):
    _quiet(state)
    target = next(d for d in discoveries.stirring(state))
    before = state.nation.insight[target.id]
    assert game.choose(state, 0, f"new:pursue:{target.id}")
    game.end_year(state)
    assert state.nation.insight.get(target.id, target.cost) > before


def test_forms_of_exchange_bring_their_own_means(state):
    discoveries.learn(state, "exchange", "tokens")
    cats = discoveries.categories(state.nation)
    assert "tokens" in cats
    assert discoveries.category_name(state.nation, "tokens") in (
        "shells",
        "polished stones",
        "beads",
    )
    assert "trader" in rebirth_weights(state.nation)


def test_roles_appear_and_fade_with_new_ways(state):
    assert "planter" not in rebirth_weights(state.nation)
    gatherers = rebirth_weights(state.nation)["gatherer"]
    discoveries.learn(state, "cultivation", "common_fields")
    weights = rebirth_weights(state.nation)
    assert "planter" in weights and weights["gatherer"] < gatherers


def test_how_leaders_are_chosen_can_change(state):
    discoveries.learn(state, "council", "lineage")
    assert state.nation.succession == "lineage"
    assert station_title(state.player, state.nation) == "Chief"


def test_habit_prefills_slots(state):
    state.player.tendencies = {t: -0.5 for t in tendencies.TAGS}
    state.player.tendencies["generous"] = 1.0
    game.begin_year(state)
    assert "share_food" in state.defaults or "open_stores" in state.defaults
    state.player.tendencies = {t: 0.0 for t in tendencies.TAGS}
    game.begin_year(state)
    assert state.defaults == []


def test_choosing_strengthens_and_overriding_habit_weakens(state):
    player = state.player
    player.tendencies = {t: 0.0 for t in tendencies.TAGS}
    _quiet(state)
    state.plan = ["call_together", None, None]
    state.defaults = ["share_food"]
    game.end_year(state)
    assert player.tendencies["caring"] > 0
    assert player.tendencies["generous"] < 0


def test_skipping_an_obligation_costs_karma():
    def year(take):
        s = game.new_game(seed=99)
        _quiet(s)
        s.events = [EventInstance("stranger", "x", obligation="welcome_stranger", penalty=0.05)]
        s.plan = ["event:0" if take else None, None, None]
        before = s.soul.karma
        game.end_year(s)
        return s.soul.karma - before

    assert year(take=True) > 0 > year(take=False)


def test_an_alternative_answer_meets_the_obligation_with_its_own_weight(state):
    n = next(iter(state.neighbours.values()))
    n.met = True
    _quiet(state)
    state.events = [
        EventInstance(
            "raid",
            "raid",
            obligation="answer_raid",
            penalty=0.06,
            data={"neighbour": n.id, "also": ["avenge_raid"]},
        )
    ]
    before = n.relations
    state.plan = ["avenge_raid", None, None]
    karma = state.soul.karma
    game.end_year(state)
    assert n.relations < before
    assert state.soul.karma < karma


def test_hidden_ideas_never_appear_in_option_text(state):
    for opt in game.options(state):
        text = f"{opt.name} {opt.text} {opt.blurb}".lower()
        assert "karma" not in text and "rebirth" not in text


def test_obligations_stop_the_years_from_passing(state):
    _quiet(state)
    seen = False
    for _ in range(40):
        report = game.end_year(state)
        if report.life_ended:
            break
        if any(e.obligation for e in state.events):
            assert "Something is expected of you." in report.interrupts
            seen = True
            break
        state.plan = [None] * ACTION_SLOTS
    assert seen


def test_life_ends_and_next_begins_among_the_same_people(state):
    name = state.nation.name
    old = state.player
    old.death_age = old.age(state.year)
    report = game.end_year(state)
    assert report.life_ended and not old.alive
    assert state.soul.lives[-1]["name"] == old.full_name
    assert state.nation.leader_id != old.id  # someone else leads
    lines = game.begin_next_life(state)
    new = state.player
    assert new.id != old.id and new.alive and new.is_player and not old.is_player
    assert new.age(state.year) == ADULT_AGE
    assert state.nation.name == name
    assert lines and "born" in lines[0]


def test_rebirth_role_is_random():
    roles = set()
    for seed in range(25):
        s = game.new_game(seed=seed)
        s.player.death_age = s.player.age(s.year)
        game.end_year(s)
        game.begin_next_life(s)
        roles.add(s.player.station)
    assert len(roles) >= 3


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


def test_save_and_load_round_trip(tmp_path, state, play):
    play(state, 8)
    path = tmp_path / "save.json"
    save.save(state, path)
    loaded = save.load(path)
    assert json.dumps(loaded.to_dict(), sort_keys=True) == json.dumps(
        state.to_dict(), sort_keys=True
    )
    # the RNG is restored too, so both copies play on identically
    play(state, 4, seed=5)
    play(loaded, 4, seed=5)
    assert json.dumps(loaded.to_dict(), sort_keys=True) == json.dumps(
        state.to_dict(), sort_keys=True
    )


def test_from_dict_ignores_unknown_keys(state):
    data = state.to_dict()
    data["something_new"] = 1
    data["nation"]["retired_field"] = 2
    assert GameState.from_dict(data).year == state.year


def test_long_game_stays_sane(play):
    s = play(game.new_game(seed=3), 200, seed=3)
    assert len(s.soul.lives) >= 3
    assert 150 < s.total_population() < 60000
    assert 0 <= s.nation.cohesion <= 100 and 0 <= s.nation.lore <= 100
    assert len(s.nation.known) > len(discoveries.START_KNOWN) + 5
    assert any(n.met for n in s.neighbours.values())
    assert len(s.characters) < 600
    assert s.player.alive


# --- leading from wherever you are --------------------------------------------


def _not_leading(state):
    """Make the player an ordinary hunter, with someone else leading."""
    from sankhara.sim.people import create_character

    leader = create_character(state, "leader", state.seat.id, state.year - 40)
    state.nation.leader_id = leader.id
    state.player.station = "hunter"
    return leader


def test_anyone_can_begin_the_peoples_work(state):
    _not_leading(state)
    _quiet(state)
    keys = {o.key for o in game.options(state) if o.kind == "project"}
    assert any(k.startswith("new:gathering:") for k in keys)
    key = next(k for k in keys if k.startswith("new:gathering:"))
    assert game.choose(state, 0, key)
    game.end_year(state)
    project = state.projects_of(state.player_id)[0]
    assert project.common and project.started_by == state.player.full_name


def test_helping_with_anothers_work_speeds_it(state):
    from sankhara.sim import projects

    leader = _not_leading(state)
    _quiet(state)
    option = next(o for o in projects.options_for(state, leader) if o.definition.id == "gathering")
    project = projects.start(state, leader, option)
    key = f"join:{project.id}"
    assert any(o.key == key for o in game.options(state))
    assert game.choose(state, 0, key)
    state.nation.stores.set("hands", 99)
    leader.means.set("hands", 99)
    game.end_year(state)
    assert state.player_id in project.helpers
    assert project.done > 1.0  # more than the leader alone
    assert state.plan[0] == f"p:{project.id}"  # and it keeps the slot


def test_calling_others_to_a_work_brings_help(state):
    _quiet(state)
    game.choose(state, 0, "new:teach_young:")
    game.end_year(state)
    project = state.projects_of(state.player_id)[0]
    state.events = []
    state.player.means.set("regard", 60)
    assert game.choose(state, 1, f"rally:{project.id}")
    game.end_year(state)
    assert project.support > 0
    assert any("called on others" in line for line in state.log[-2:])


def test_work_outlives_the_life_that_began_it(state):
    _quiet(state)
    game.choose(state, 0, "new:teach_young:")
    game.end_year(state)
    project = state.projects_of(state.player_id)[0]
    first = state.player.full_name
    state.player.death_age = state.player.age(state.year)
    state.events = []
    assert game.end_year(state).life_ended
    assert str(project.id) in state.projects
    lines = game.begin_next_life(state)
    if str(project.id) in state.projects:
        # still unfinished: the new life hears of it and can take part
        assert any(first in line and "unfinished" in line.lower() for line in lines)
        threads = [o for o in game.options(state) if o.thread]
        assert threads and threads[0].project.id == project.id
    else:
        # finished while the new character grew up, and remembered
        assert any(first in e["names"] for e in state.legacy)


def test_finished_work_is_remembered_in_the_life_summary(state):
    _quiet(state)
    game.choose(state, 0, "new:teach_young:")
    for _ in range(12):
        state.player.means.set("hands", 10)
        game.end_year(state)
        state.events = []
        if not any(p.kind == "teach_young" for p in state.projects.values()):
            break
    assert state.legacy
    state.player.death_age = state.player.age(state.year)
    game.end_year(state)
    assert state.soul.lives[-1]["legacy"]


def test_anyone_can_speak_for_how_a_custom_should_be():
    urged = 0
    for seed in range(20):
        s = game.new_game(seed=seed)
        _not_leading(s)
        _quiet(s)
        d = discoveries.DISCOVERIES["gifts"]
        s.nation.insight[d.id] = d.cost
        game.end_year(s)
        assert s.pending_choice == "gifts" and s.pending_mode == "voice"
        s.player.means.set("regard", 100)
        line = game.choose_form(s, "feasts")
        urged += s.nation.known["gifts"] == "feasts"
        assert "urged" in line or "spoke" in line
    assert urged >= 12  # a respected voice usually carries
