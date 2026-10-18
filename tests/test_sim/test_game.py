import json

from sankhara.sim import actions, discoveries, events, game, people, save, tendencies
from sankhara.sim.state import EventInstance, GameState
from sankhara.sim.stations import ACTION_SLOTS, ADULT_AGE, rebirth_weights, station_title


def _quiet(state):
    """No events and nothing planned, so a test controls the year."""
    state.events = []
    state.plan = [None] * ACTION_SLOTS


def _matter(state, kind, text="", **kw):
    """Put a matter in front of the player this year. Returns it."""
    event = events.offer(state, state.player, EventInstance(kind, text or kind, **kw))
    state.events.append(event)
    return event


def _answer(event, action_id):
    return events.answer_key(event, action_id)


def test_new_game_starts_as_a_young_leader_of_a_small_band(state):
    player = state.player
    assert player.station == "leader"
    assert 22 <= player.age(state.year) <= 30
    assert state.nation.leader_id == player.id
    assert 100 < state.total_population() < 1500
    assert len(state.settlements) == 3
    assert all(s.kind == "camp" for s in state.settlements.values())
    assert set(state.nation.known) == set(discoveries.START_KNOWN)
    assert discoveries.stirring(state)
    assert len(state.neighbours) == 3 and not any(n.met for n in state.neighbours.values())
    assert sum(1 for c in state.living() if c.is_elder) >= 4
    assert state.plan == [None] * ACTION_SLOTS  # nothing is chosen for the player


def test_the_first_leader_earned_it():
    """Leading is not handed down: the first life's story is of something they did."""
    for seed in range(12):
        s = game.new_game(seed=seed)
        story = s.log[0].lower()
        assert "mother" not in story and "father" not in story
        assert "you" in story
        player = s.player
        assert player.mother_id is None or s.character(player.mother_id).station != "leader"


def test_there_is_no_money_or_trade_goods_at_the_start(state):
    assert discoveries.categories(state.nation) == ["food", "hands", "regard"]
    text = json.dumps(state.to_dict()).lower()
    assert "coin" not in text and "goods" not in text


def test_options_come_in_three_groups(state):
    _quiet(state)
    _matter(state, "idler", target_id=None)
    groups = [o.group for o in game.options(state)]
    assert set(groups) == {"works", "matters", "own"}
    assert groups == sorted(groups, key=["matters", "works", "own"].index)


def test_a_matter_offers_ways_to_meet_it_and_expected_ones_come_first(state):
    _quiet(state)
    _matter(state, "idler")
    stranger = _matter(state, "stranger")
    assert stranger.expected and stranger.answers == ["welcome_stranger", "send_on"]
    answers = [o for o in game.options(state) if o.kind == "answer"]
    assert answers[0].expected and answers[0].blurb == "stranger"
    assert {o.key for o in answers if o.expected} == {
        _answer(stranger, "welcome_stranger"),
        _answer(stranger, "send_on"),
    }


def test_answers_depend_on_role(state):
    _quiet(state)
    state.nation.stores.set("food", 200)
    hunger = _matter(state, "hunger")
    assert "open_stores" in hunger.answers and "bring_food" not in hunger.answers
    state.player.station = "hunter"
    hunger = _matter(state, "hunger")
    assert "bring_food" in hunger.answers and "open_stores" not in hunger.answers


def test_lasting_cares_never_ask_you_to_be_selfish_or_harsh():
    """Taking more than your share, shaming, hoarding knowledge: those come up only as one
    way of meeting a real matter, never as an item on a menu."""
    for care in (a for a in actions.ACTION_LIST if a.care):
        assert not {"acquisitive", "harsh", "indulgent"} & set(care.tags), care.id


def test_choose_rejects_duplicates_and_unaffordable(state):
    _quiet(state)
    state.player.tendencies = {}
    assert game.choose(state, 0, "go_among")
    assert not game.choose(state, 1, "go_among")
    state.player.means.set("hands", 0)
    assert not game.choose(state, 0, "go_among")
    assert game.choose(state, 0, None)
    assert state.plan[0] is None


def test_costs_are_cumulative_across_slots(state):
    _quiet(state)
    state.player.tendencies = {}
    state.player.means.set("regard", 6)
    discord = _matter(state, "discord")
    assert game.choose(state, 0, _answer(discord, "call_together"))  # 4 regard
    assert not game.choose(state, 1, _answer(discord, "drive_out"))  # 3 regard, only 2 left


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


def test_nothing_is_chosen_for_the_player(state):
    state.player.tendencies = {t: -0.5 for t in tendencies.TAGS}
    state.player.tendencies["generous"] = 1.0
    game.begin_year(state)
    assert state.plan == [None] * ACTION_SLOTS


def test_choosing_strengthens_inclinations(state):
    player = state.player
    player.tendencies = {t: 0.0 for t in tendencies.TAGS}
    _quiet(state)
    state.plan = ["go_among", None, None]
    game.end_year(state)
    assert player.tendencies["caring"] > 0
    assert player.tendencies["generous"] == 0


def test_a_chosen_deed_is_kept_up_until_changed(state):
    _quiet(state)
    state.player.means.set("hands", 50)
    assert game.choose(state, 2, "rest")
    game.end_year(state)
    assert state.plan[2] == "rest"
    game.choose(state, 2, None)
    game.end_year(state)
    assert state.plan == [None] * ACTION_SLOTS


def test_an_answer_is_kept_up_while_the_matter_lasts(state):
    _quiet(state)
    discord = _matter(state, "discord")
    key = _answer(discord, "settle_quarrels")
    assert game.choose(state, 0, key)
    state.events = [events.offer(state, state.player, EventInstance("discord", "again"))]
    game.replan(state, list(state.plan))
    assert state.plan[0] == key
    state.events = []  # the quarrels are over
    game.replan(state, list(state.plan))
    assert state.plan == [None] * ACTION_SLOTS


def test_a_finished_work_leaves_its_slot_empty(state):
    _quiet(state)
    state.player.tendencies = {t: 1.0 for t in tendencies.TAGS}  # habit chooses nothing
    assert game.choose(state, 0, "new:teach_young:")
    for _ in range(12):
        state.player.means.set("hands", 10)
        game.end_year(state)
        if not state.projects_of(state.player_id):
            break
    assert not state.projects_of(state.player_id)
    assert state.plan[0] is None


def test_letting_the_years_slip_by_idle_weighs_on_a_life():
    def drift(attended, plan):
        s = game.new_game(seed=5)
        _quiet(s)
        s.plan = list(plan)
        before = s.soul.karma
        game.end_year(s, attended=attended)
        return s.soul.karma - before

    idle = [None] * ACTION_SLOTS
    assert drift(True, idle) > drift(False, ["rest", None, None]) > drift(False, idle)


def test_skipping_an_obligation_costs_karma():
    def year(take):
        s = game.new_game(seed=99)
        _quiet(s)
        stranger = _matter(s, "stranger")
        s.plan = [_answer(stranger, "welcome_stranger") if take else None, None, None]
        before = s.soul.karma
        game.end_year(s)
        return s.soul.karma - before

    assert year(take=True) > 0 > year(take=False)


def test_an_alternative_answer_meets_the_obligation_with_its_own_weight(state):
    n = next(iter(state.neighbours.values()))
    n.met = True
    _quiet(state)
    raid = _matter(state, "raid", data={"neighbour": n.id, "camp": state.seat.name})
    assert raid.expected and "avenge_raid" in raid.answers
    before = n.relations
    state.plan = [_answer(raid, "avenge_raid"), None, None]
    karma = state.soul.karma
    game.end_year(state)
    assert n.relations < before
    assert state.soul.karma < karma


def test_hidden_ideas_never_appear_in_option_text(state):
    for opt in game.options(state):
        text = f"{opt.name} {opt.text} {opt.blurb}".lower()
        assert "karma" not in text and "rebirth" not in text


def test_obligations_are_noticed(state):
    _quiet(state)
    seen = False
    for _ in range(40):
        report = game.end_year(state)
        if report.life_ended:
            break
        if game.unmet(state):
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


def test_a_second_era_of_ideas_comes_after_the_first(play):
    """The first ways of living arrive over a couple of hundred years; the later ideas
    need them (and more people, or trouble) first, so they come after."""
    s = play(game.new_game(seed=3), 150, seed=3)
    later = [d for d in discoveries.LATER_IDEAS if d in s.nation.known]
    first = [d for d in s.nation.known if d not in discoveries.LATER_IDEAS]
    assert len(later) <= 2 and len(first) >= 12
    for did in discoveries.LATER_IDEAS:
        d = discoveries.DISCOVERIES[did]
        assert d.requires or d.requires_any or d.condition, did
        assert did in discoveries.QUESTIONS


def test_walls_and_warriors_make_raids_rarer(state):
    from sankhara.sim.peoples import raid_chance

    n = next(iter(state.neighbours.values()))
    n.met = True
    n.relations = -0.6
    before = raid_chance(state, n)
    assert before > 0
    discoveries.learn(state, "walls")
    assert raid_chance(state, n) < before
    discoveries.learn(state, "warriors", "war_band")
    assert raid_chance(state, n) < before * 0.5


def test_villages_grow_into_towns(state):
    from sankhara.sim import nation

    discoveries.learn(state, "settling")
    nation.economy_year(state)
    assert all(s.kind == "village" for s in state.settlements.values())
    big = state.seat
    big.population = nation.TOWN_SIZE + 100
    nation.economy_year(state)
    assert big.kind == "village"  # the people have no notion of a town yet
    discoveries.learn(state, "towns")
    big.population = nation.TOWN_SIZE + 100
    nation.economy_year(state)
    assert big.kind == "town"
    assert any(s.kind == "village" for s in state.settlements.values())


# --- how the people decide ----------------------------------------------------------


def _ripen(state, did):
    d = discoveries.DISCOVERIES[did]
    state.nation.insight[d.id] = d.cost
    _quiet(state)
    game.end_year(state)
    assert state.pending_choice == did


def test_under_a_council_nobody_settles_a_custom_alone(state):
    """A leader decides matters of custom, unless the people have a council of elders:
    then the elders' leanings decide and the leader (or an elder) only speaks louder."""
    discoveries.learn(state, "council", "elders")
    _ripen(state, "gifts")
    assert state.pending_mode == "voice"
    assert game._voice(state) > 1 + state.player.means.get("regard") / game.VOICE_WEIGHT
    assert {c.id for c in discoveries.deciders(state)} <= {
        c.id for c in state.living() if c.is_elder or c.id == state.nation.leader_id
    }


def test_a_chief_who_holds_the_people_settles_every_custom(state):
    discoveries.learn(state, "council", "strongest")
    _ripen(state, "burial")  # a matter of lore, which a leader would not otherwise decide
    assert state.pending_mode == "decide"
    state.player.station = "hunter"
    assert game._voice(state) < 1 + state.player.means.get("regard") / game.VOICE_WEIGHT


def test_what_is_owed_to_the_leader_keeps_them(state):
    from sankhara.sim import nation

    leader = state.leader
    leader.means.set("food", 0)
    nation.households_year(state)
    before = leader.means.get("food")
    leader.means.set("food", 0)
    discoveries.learn(state, "tribute", "leaders_share")
    nation.households_year(state)
    assert leader.means.get("food") > before


def test_a_band_set_apart_to_fight_is_a_role_to_be_born_into(state):
    assert "warrior" not in rebirth_weights(state.nation)
    discoveries.learn(state, "warriors", "all_fight")
    assert "warrior" not in rebirth_weights(state.nation)
    discoveries.learn(state, "warriors", "war_band")
    assert "warrior" in rebirth_weights(state.nation)


def test_keeping_watch_turns_raiders_back(state):
    from sankhara.sim.peoples import raid_chance

    n = next(iter(state.neighbours.values()))
    n.met = True
    n.relations = -0.6
    before = raid_chance(state, n)
    _not_leading(state)
    state.player.station = "warrior"
    _quiet(state)
    assert game.choose(state, 0, "keep_watch")
    game.end_year(state)
    assert raid_chance(state, n) < before
    raid = _matter(state, "raid", data={"neighbour": n.id, "camp": state.seat.name})
    assert raid.expected and "stand_guard" in raid.answers and "answer_raid" not in raid.answers


# --- those around you ----------------------------------------------------------------


def test_feuds_are_between_families_you_know(state):
    from sankhara.sim.people import members

    _quiet(state)
    feud = events.EVENT_DEFS["feud"].build(state, state.player, state.rng())
    state.events.append(events.offer(state, state.player, feud))
    known = {c.family_name for c in state.living()}
    assert feud.data["a"] in known and feud.data["b"] in known
    a, b = feud.data["a"], feud.data["b"]
    state.plan = [_answer(feud, "side_with"), None, None]
    game.end_year(state)
    assert all(c.feels(state.player_id) > 0 for c in members(state, a))
    assert all(c.feels(state.player_id) < 0 for c in members(state, b) if c.alive)


def test_a_rival_for_the_peoples_trust_is_a_matter_for_the_leader(state):
    me = state.player
    other = next(c for c in state.living() if c.id != me.id and c.age(state.year) >= 20)
    other.means.set("regard", 100)
    assert events.rival(state) is other
    _quiet(state)
    matter = _matter(state, "rival", target_id=other.id, data={"rival": other.name})
    assert matter.answers == ["win_over", "make_room", "face_down"]
    names = [o.name for o in game.options(state) if o.kind == "answer"]
    assert f"Win {other.name} over" in names
    me.means.set("regard", 300)
    state.plan = [_answer(matter, "face_down"), None, None]
    for _ in range(20):  # the stronger standing usually wins the exchange
        before = other.means.get("regard")
        game.end_year(state)
        _quiet(state)
        if other.means.get("regard") < before:
            break
        other.means.set("regard", 100)
        matter = _matter(state, "rival", target_id=other.id, data={"rival": other.name})
        state.plan = [_answer(matter, "face_down"), None, None]
    assert other.means.get("regard") < 100
    assert other.feels(me.id) < 0


def test_others_ask_you_to_take_sides(state):
    leader = _not_leading(state)
    me = state.player
    other = next(
        c for c in state.living() if c.id not in (me.id, leader.id) and c.age(state.year) >= 20
    )
    other.means.set("regard", 100)
    leader.means.set("regard", 50)
    _quiet(state)
    matter = _matter(state, "take_sides", target_id=other.id, data={"rival": other.name})
    assert matter.answers == ["back_rival", "back_leader", "stay_out"]
    state.plan = [_answer(matter, "back_rival"), None, None]
    game.end_year(state)
    assert other.feels(me.id) > 0 > leader.feels(me.id)


def test_around_you_shows_the_leader_and_those_in_your_camp(state):
    leader = _not_leading(state)
    around = game.around_you(state)
    assert around and around[0][0] is leader
    assert len(around) <= game.AROUND_YOU
    assert all(c.settlement_id == state.player.settlement_id for c, _ in around[1:])
    assert not any(c.is_player for c, _ in around)


# --- settling customs anew -------------------------------------------------------


def test_a_custom_can_be_settled_anew_and_the_old_form_undone(state):
    discoveries.learn(state, "gifts", "feasts")
    discoveries.learn(state, "exchange", "tokens")
    discoveries.learn(state, "council", "lineage")
    assert state.nation.succession == "lineage" and "tokens" in discoveries.categories(state.nation)
    state.year += discoveries.RESETTLE_AFTER
    assert {did for did, _ in discoveries.customs(state)} >= {"gifts", "exchange", "council"}
    discoveries.resettle(state, "exchange", "favours")
    discoveries.resettle(state, "council", "elders")
    cats = discoveries.categories(state.nation)
    assert "favours" in cats and "tokens" not in cats
    assert state.nation.succession == "council"
    assert station_title(state.player, state.nation) == "First Elder"
    assert not any(did == "exchange" for did, _ in discoveries.customs(state))  # too soon again


def test_calling_for_a_custom_to_change_lets_you_decide_it(state):
    """A people's work: when it is done, whoever led it (here you) decides the new form."""
    discoveries.learn(state, "gifts", "feasts")
    state.year += discoveries.RESETTLE_AFTER
    game.begin_year(state)
    _quiet(state)
    assert game.choose(state, 0, "new:reform:gifts")
    report = None
    for _ in range(10):
        state.events = []
        state.player.means.set("hands", 10)
        state.player.means.set("regard", 50)
        report = game.end_year(state)
        if state.pending_choice:
            break
    assert state.pending_choice == "gifts" and state.pending_mode == "decide"
    assert any("how the people give and receive" in i for i in report.interrupts)
    line = game.choose_form(state, "binding_gifts")
    assert state.nation.known["gifts"] == "binding_gifts"
    assert "decided anew" in line and "feasts for renown" in line
    assert any("as you decided" in e["text"] for e in state.legacy)


def test_when_someone_else_calls_for_change_you_can_only_speak(state):
    from sankhara.sim import projects

    leader = _not_leading(state)
    discoveries.learn(state, "gifts", "feasts")
    state.year += discoveries.RESETTLE_AFTER
    _quiet(state)
    state.player.means.set("regard", 10)  # not respected enough to call for it yourself
    assert not any(o.key.startswith("new:reform:") for o in game.options(state))
    option = next(
        o
        for o in projects.options_for(state, leader)
        if o.definition.id == "reform" and o.target == "gifts"
    )
    project = projects.start(state, leader, option)
    project.done = project.needed
    game.end_year(state)
    assert state.pending_choice == "gifts" and state.pending_mode == "voice"


def test_a_change_nobody_speaks_on_follows_the_peoples_leanings(state):
    discoveries.learn(state, "gifts", "feasts")
    state.due_choices.append({"did": "gifts", "by": None})
    for c in state.living():
        c.tendencies = {"generous": 1.0, "caring": 1.0, "ambitious": -1.0, "indulgent": -1.0}
    _quiet(state)
    game.end_year(state)  # it comes up...
    assert state.pending_choice == "gifts"
    _quiet(state)
    game.end_year(state)  # ...and nobody answers
    assert state.pending_choice is None
    assert state.nation.known["gifts"] == "binding_gifts"
    assert any("settled anew how they give and receive" in line for line in state.log)


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


def _living_leader(state):
    leader = state.leader
    leader.death_age = 200
    leader.health = 90
    return leader


def test_the_people_can_turn_from_a_living_leader(state):
    """Leadership is earned: someone the people look to far more can take it from a
    leader who still lives."""
    leader = _living_leader(state)
    leader.is_player = False
    state.player_id = next(c.id for c in state.living() if c.id != leader.id)
    rival = state.player
    rival.birth_year = state.year - 30
    rival.is_player = True
    rival.means.set("regard", 400)
    leader.means.set("regard", 10)
    for _ in range(60):
        rival.means.set("regard", 400)
        if people.leadership_year(state):
            break
    assert state.nation.leader_id == rival.id
    assert leader.station != "leader" and leader.alive


def test_an_old_leader_gives_way(state):
    leader = _living_leader(state)
    leader.birth_year = state.year - 70
    for _ in range(60):
        if people.leadership_year(state):
            break
    assert state.nation.leader_id != leader.id and leader.is_elder


def test_a_custom_of_lineage_keeps_it_in_the_family(state):
    discoveries.learn(state, "council", "lineage")
    leader = _living_leader(state)
    for c in state.living():
        if c is not leader:
            c.means.set("regard", 400)
    for _ in range(30):
        people.leadership_year(state)
    assert state.nation.leader_id == leader.id


def test_anyone_respected_can_ask_to_lead(state):
    leader = _living_leader(state)
    me = next(c for c in state.living() if c.id != leader.id and c.age(state.year) >= 20)
    state.player.is_player = False
    me.is_player = True
    state.player_id = me.id
    me.means.set("regard", 10)
    talk_of_leading = events.EVENT_DEFS["could_lead"].chance
    assert talk_of_leading(state, me) == 0
    me.means.set("regard", 300)
    leader.means.set("regard", 5)
    assert talk_of_leading(state, me) > 0
    _quiet(state)
    talk = _matter(state, "could_lead")
    assert talk.answers == ["stand_forward", "back_leader"]
    assert game.choose(state, 0, _answer(talk, "stand_forward"))
    report = game.end_year(state)
    assert state.nation.leader_id == me.id
    assert "The people have turned to you to lead them." in report.interrupts


def test_respected_lives_often_come_to_lead(play):
    """Over a long game the player leads in some lives that did not begin as leader.
    (It happens in most games, not all, so a couple of seeds are tried.)"""
    led = set()
    for seed in (20, 21, 22):
        s = game.new_game(seed=seed)
        for _ in range(300):
            play(s, 1, seed=s.year)
            if s.player.station == "leader" and len(s.soul.lives) > 0:
                led.add((seed, s.player_id))
        if led:
            break
    assert led
