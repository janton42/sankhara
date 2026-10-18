"""One-year deeds: what a character can do with a slot of attention this year.

There are two kinds. **Cares** are the lasting ways a life spends itself (your
kin, your craft, the songs): offered every year and kept up until changed.
**Answers** are ways of meeting a matter at hand (a hungry camp, a quarrel, a
stranger at the fire; see `events.py`): offered only while the matter lasts, and
which ones depend on the character's role. No deed is labelled good or bad; each
carries inclination tags and a hidden karma value for the intention behind it,
never its outcome.

Every role reaches differently: the leader's deeds draw on the people's common
stores and touch everyone; the others draw on their own family's means and touch
those nearby. Longer undertakings are projects (`projects.py`). Effects receive
a Ctx and return a short sentence for the chronicle.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from sankhara.sim import discoveries, tendencies
from sankhara.sim.nation import adjust_settlements, advance, clamp, land_richness, people_scale
from sankhara.sim.people import (
    FRAIL_HEALTH,
    LEADER_AGE,
    STEP_ASIDE_AGE,
    family_of,
    make_leader,
    members,
    standing,
)
from sankhara.sim.stations import ADULT_AGE, STATIONS

FOOD_ROLES = ("hunter", "gatherer", "fisher", "planter", "herder")


@dataclass
class Ctx:
    state: object
    char: object
    rng: object
    event: object = None

    @property
    def nation(self):
        return self.state.nation

    @property
    def settlement(self):
        return self.state.settlement(self.char.settlement_id) or self.state.seat


@dataclass(frozen=True)
class Action:
    id: str
    name: str  # an answer's name may use the matter's data, e.g. {a}
    text: str
    stations: tuple  # empty = open to every role
    tags: tuple
    karma: float  # hidden: the intention, not the outcome
    effect: Callable = field(repr=False)
    cost: dict = field(default_factory=dict)
    scope: str = "own"  # "people" spends the common stores when the leader acts
    requires: Callable | None = field(default=None, repr=False)
    care: bool = False  # a lasting care, offered every year; otherwise an answer to a matter

    def label(self, event=None):
        """The name, with the matter's particulars filled in."""
        try:
            return self.name.format(**(event.data if event else {}))
        except KeyError:
            return self.name


OWN_SHARE = 0.5


def budget_for(state, char, action):
    if action.scope == "people" and char.station == "leader":
        return state.nation.stores
    return char.means


def effective_cost(state, char, item):
    """What an action or project costs this character, after inclination (and, when it
    draws on the common stores, the size of the people)."""
    mult = tendencies.cost_multiplier(char.tendencies, item.tags)
    if budget_for(state, char, item) is state.nation.stores:
        mult *= people_scale(state)
    elif item.scope == "people":
        mult *= OWN_SHARE  # one family beginning the people's work gives what it can
    return {k: max(1, round(v * mult)) for k, v in item.cost.items()}


def open_to(state, char, action):
    return (not action.stations or char.station in action.stations) and (
        action.requires is None or action.requires(state, char)
    )


# --- helpers ---------------------------------------------------------------


def _family(ctx):
    return [c for _, c in family_of(ctx.state, ctx.char)]


def _local(ctx, cohesion=0.0, plenty=0.0, camp=None):
    camp = camp or ctx.settlement
    adjust_settlements(ctx.state, cohesion=cohesion, plenty=plenty, only=camp.id)


def _people(ctx, cohesion=0.0, plenty=0.0):
    adjust_settlements(ctx.state, cohesion=cohesion, plenty=plenty)


def heal(char, amount):
    char.health = clamp(char.health + amount)


def neighbour(ctx):
    family = {c.id for c in _family(ctx)}
    near = [
        c
        for c in ctx.state.living()
        if c.settlement_id == ctx.char.settlement_id
        and not c.is_player
        and c.id != ctx.char.id
        and c.id not in family
        and c.age(ctx.state.year) >= ADULT_AGE
    ]
    return ctx.rng.choice(near) if near else None


def _target(ctx):
    """The person the matter is about, or someone nearby."""
    who = ctx.state.character(ctx.event.target_id) if ctx.event else None
    return who if who and who.alive else neighbour(ctx)


def _event_camp(ctx):
    camp = ctx.state.settlement(ctx.event.settlement_id) if ctx.event else None
    return camp or ctx.settlement


def _richness(ctx, land):
    return land_richness(ctx.state, ctx.settlement, land) * ctx.state.modifiers.get("harvest", 1.0)


def _own_land(ctx):
    return _richness(ctx, STATIONS[ctx.char.station].land)


def _gain(ctx, category, amount):
    ctx.char.means.add({category: amount})


def _nudge_insight(ctx, domain, amount):
    options = [d for d in discoveries.available(ctx.state) if d.domain == domain]
    if options:
        discoveries.add_insight(ctx.state, ctx.rng.choice(options).id, amount)


# --- cares: anyone -------------------------------------------------------------


def _care_family(ctx):
    for c in _family(ctx):
        heal(c, 5)
        c.adjust_affinity(ctx.char.id, 0.1)
        ctx.char.adjust_affinity(c.id, 0.05)
    return "Your family was looked after."


def _rest(ctx):
    heal(ctx.char, 10)
    return "You rested and recovered some strength."


def _sit_alone(ctx):
    heal(ctx.char, 4)
    _nudge_insight(ctx, "lore", 2)
    return "You spent long evenings alone at the edge of the camp, listening."


# --- cares: each role ------------------------------------------------------------


def _go_among(ctx):
    _people(ctx, cohesion=1)
    _gain(ctx, "regard", 1)
    return "You went from camp to camp, listening to whoever wanted to talk."


def _sing_songs(ctx):
    advance(ctx.nation, "lore", 2.5)
    _gain(ctx, "regard", 1.5)
    return "The old songs were sung through the long nights, and the young learned them."


def _tend_sick(ctx):
    near = [c for c in ctx.state.living() if c.settlement_id == ctx.char.settlement_id]
    for c in near:
        heal(c, 4)
    _local(ctx, cohesion=1)
    _gain(ctx, "regard", 2)
    ctx.state.modifiers["plague"] = ctx.state.modifiers.get("plague", 0) * 0.8
    return "You went from shelter to shelter with your herbs and your songs."


def _hunt(ctx):
    _gain(ctx, "food", 8 * _richness(ctx, "animal"))
    if ctx.rng.random() < 0.05:
        heal(ctx.char, -12)
        return "You hunted well, but came back torn by a beast."
    return "You hunted and brought meat home."


def _forage(ctx):
    _gain(ctx, "food", 8 * _richness(ctx, "plant"))
    return "You knew where to look, and came home laden."


def _show_plants(ctx):
    _nudge_insight(ctx, "land", 4)
    advance(ctx.nation, "lore", 0.5)
    _gain(ctx, "regard", 1)
    return "The children learned which plants feed and which kill."


def _make_tools(ctx):
    _gain(ctx, "regard", 3)
    _local(ctx, plenty=1.5)
    return "Your blades and scrapers went to whoever needed them."


def _fish(ctx):
    _gain(ctx, "food", 9 * _richness(ctx, "water"))
    return "The water was generous."


def _tend_fields(ctx):
    _gain(ctx, "food", 11 * _richness(ctx, "plant"))
    return "You worked your ground from planting to harvest."


def _help_neighbours(ctx):
    who = neighbour(ctx)
    _local(ctx, cohesion=1.5)
    _gain(ctx, "regard", 1.5)
    if who:
        who.adjust_affinity(ctx.char.id, 0.2)
        who.means.add({"food": 6})
        return f"You helped {who.name} bring in a harvest."
    return "You helped wherever hands were short."


def _tend_herd(ctx):
    _gain(ctx, "food", 9 * _richness(ctx, "animal"))
    return "Your beasts grew fat."


def _trade(ctx):
    _gain(ctx, "food", 10)
    _gain(ctx, "regard", 1)
    return "You carried things from those who had them to those who wanted them."


def _keep_watch(ctx):
    ctx.nation.watched_until = ctx.state.year + 1
    _people(ctx, cohesion=0.5)
    _gain(ctx, "regard", 1.5)
    return "You walked the edges of the camps by night, and people slept the better for it."


def _train_young(ctx):
    _nudge_insight(ctx, "craft", 2)
    _local(ctx, cohesion=1)
    _gain(ctx, "regard", 1)
    return "The young learned to hold a line and to loose together."


# --- answers: hunger and plenty ---------------------------------------------------


def _open_stores(ctx):
    relief = 20 * people_scale(ctx.state)
    ctx.state.modifiers["relief"] = ctx.state.modifiers.get("relief", 0.0) + relief
    _people(ctx, cohesion=1.5)
    return "The common stores were opened to whoever needed them."


def _share_food(ctx):
    _local(ctx, cohesion=1.5)
    _gain(ctx, "regard", 1)
    who = neighbour(ctx)
    if who:
        who.adjust_affinity(ctx.char.id, 0.15)
        heal(who, 5)
    return "Those with little ate a little better."


def _bring_food(ctx):
    food = 8 * _own_land(ctx)
    ctx.state.modifiers["relief"] = ctx.state.modifiers.get("relief", 0.0) + food
    _local(ctx, cohesion=1)
    _gain(ctx, "regard", 1)
    return "You brought what you could get to the hungry."


def _keep_close(ctx):
    _gain(ctx, "food", 3)
    return "Your family's food stayed by your own fire."


def _great_hunt(ctx):
    food = 15 * _richness(ctx, "animal") * people_scale(ctx.state)
    ctx.nation.stores.add({"food": food})
    _gain(ctx, "regard", 2)
    if ctx.rng.random() < 0.08:
        heal(ctx.char, -15)
        return "The great hunt brought meat for all, but you were gored."
    return "The great hunt brought meat for all."


def _stock_stores(ctx):
    ctx.nation.stores.add({"food": 8 * _own_land(ctx)})
    _gain(ctx, "regard", 1.5)
    return "What you brought in went to the common stores."


def _feast_all(ctx):
    _people(ctx, cohesion=3)
    _gain(ctx, "regard", 2)
    return "All the camps feasted together, and the songs went on till dawn."


def _feast(ctx):
    heal(ctx.char, 3)
    _gain(ctx, "regard", 0.5)
    return "You ate well and laughed late into the night."


def _take_more(ctx):
    taken = min(10.0, ctx.nation.stores.get("food"))
    ctx.nation.stores.add({"food": -taken})
    _gain(ctx, "food", taken)
    _local(ctx, cohesion=-1)
    return "Your family ate better than most." if taken else "There was nothing spare to take."


def _larger_share(ctx):
    taken = min(14.0, ctx.nation.stores.get("food"))
    ctx.nation.stores.add({"food": -taken})
    _gain(ctx, "food", taken)
    _people(ctx, cohesion=-2)
    return "Your family's share grew. People noticed."


# --- answers: quarrels and who leads ----------------------------------------------


def _call_together(ctx):
    _people(ctx, cohesion=3)
    return "The camps came together; old grudges were aired and some were settled."


def _settle_quarrels(ctx):
    _people(ctx, cohesion=4)
    _gain(ctx, "regard", 1)
    return "You heard out every side, and most went away content."


def _drive_out(ctx):
    if ctx.rng.random() < 0.6:
        _people(ctx, cohesion=2)
        return "A troublemaker was driven from the camp. It was quieter afterwards."
    _people(ctx, cohesion=-2)
    return "A troublemaker was driven out. His kin have not forgiven it."


def _speak_at_fires(ctx):
    _local(ctx, cohesion=1.5)
    _gain(ctx, "regard", 1)
    return "You spoke for patience at every fire that would hear you."


def _judge_feud(ctx):
    _gain(ctx, "regard", 1)
    return "You heard both families out."


def _make_peace(ctx):
    return "You went between the two families, carrying words."


def _side_with(ctx):
    _gain(ctx, "regard", 2)
    _people(ctx, cohesion=-1)
    a = ctx.event.data.get("a", "one") if ctx.event else "one"
    b = ctx.event.data.get("b", "") if ctx.event else ""
    for c in members(ctx.state, a):
        c.adjust_affinity(ctx.char.id, 0.3)
    for c in members(ctx.state, b):
        c.adjust_affinity(ctx.char.id, -0.3)
    return f"You stood with the {a} family, and said so to anyone who asked."


# --- answers: a rival for the people's trust -------------------------------------------


def _rival_of(ctx):
    who = ctx.state.character(ctx.event.target_id) if ctx.event else None
    return who if who and who.alive else None


def _win_over(ctx):
    r = _rival_of(ctx)
    if r is None:
        return "There was no one to win over."
    r.adjust_affinity(ctx.char.id, 0.35)
    ctx.char.adjust_affinity(r.id, 0.15)
    r.means.add({"food": 6})
    _people(ctx, cohesion=1)
    return f"You sat long with {r.name}, gave gifts and listened. The talk died down."


def _make_room(ctx):
    r = _rival_of(ctx)
    if r is None:
        return "There was no one to make room for."
    r.adjust_affinity(ctx.char.id, 0.4)
    r.means.add({"regard": 3})
    _gain(ctx, "regard", -1)
    _people(ctx, cohesion=2)
    return f"You gave {r.name} a place beside you, and let them speak first at the gathering."


def _face_down(ctx):
    r = _rival_of(ctx)
    if r is None:
        return "There was no one to face down."
    mine, theirs = standing(ctx.char), standing(r)
    r.adjust_affinity(ctx.char.id, -0.3)
    if ctx.rng.random() < mine / max(1.0, mine + theirs):
        r.means.set("regard", r.means.get("regard") * 0.7)
        _gain(ctx, "regard", 3)
        return f"You faced {r.name} down before everyone, and they had nothing to say."
    ctx.char.means.set("regard", ctx.char.means.get("regard") * 0.85)
    r.means.add({"regard": 3})
    return f"You faced {r.name} down before everyone, and they answered you well. People noticed."


def _back_rival(ctx):
    r = _rival_of(ctx)
    leader = ctx.state.leader
    _gain(ctx, "regard", 1)
    if r is None:
        return "There was no one to speak for."
    r.adjust_affinity(ctx.char.id, 0.3)
    r.means.add({"regard": 2})
    if leader:
        leader.adjust_affinity(ctx.char.id, -0.3)
    return f"You spoke for {r.name} at every fire that would hear you."


def _stay_out(ctx):
    return "You kept out of it, and said so to both."


def _stand_forward(ctx):
    """Ask the people to follow you. They might, if they already look to you more than
    to the one who leads them, or that one is failing."""
    state, me = ctx.state, ctx.char
    leader = state.leader
    ratio = standing(me) / max(1.0, standing(leader) if leader else 1.0)
    chance = min(0.85, 0.05 + 0.6 * max(0.0, ratio - 0.8) + (0.3 if _failing(state) else 0.0))
    if ctx.rng.random() < chance:
        make_leader(state, me)
        return "You stood before the people and asked them to follow you, and they did."
    me.means.set("regard", me.means.get("regard") * 0.8)
    if leader:
        leader.adjust_affinity(me.id, -0.3)
    return "You stood before the people and asked them to follow you. Few did."


def _back_leader(ctx):
    leader = ctx.state.leader
    _people(ctx, cohesion=1)
    _gain(ctx, "regard", 1)
    r = _rival_of(ctx)
    if r is not None and leader is not None and r.id != leader.id:
        r.adjust_affinity(ctx.char.id, -0.2)
    if leader:
        leader.means.add({"regard": 3})
        leader.adjust_affinity(ctx.char.id, 0.2)
        return f"You told anyone who would listen that {leader.name} leads well."
    return "You told the people to wait and choose well."


# --- answers: those near you ----------------------------------------------------


def _shame_idler(ctx):
    who = _target(ctx)
    _gain(ctx, "regard", 2)
    if who:
        who.adjust_affinity(ctx.char.id, -0.3)
        heal(who, -3)
        return f"{who.name} was shamed before everyone. Some laughed."
    return "There was no one to make an example of."


def _find_work(ctx):
    who = _target(ctx)
    _local(ctx, plenty=0.5)
    if who:
        who.adjust_affinity(ctx.char.id, 0.2)
        return f"You found {who.name} work they could do, and did it with them at first."
    return "You found work for idle hands."


def _tend_relative(ctx):
    target = ctx.state.character(ctx.event.target_id) if ctx.event else None
    if target:
        heal(target, 25)
        target.adjust_affinity(ctx.char.id, 0.25)
        return f"You stayed by {target.name}'s side."
    return "You did what you could."


def _welcome_stranger(ctx):
    if ctx.rng.random() < 0.35:
        _nudge_insight(ctx, ctx.rng.choice(["land", "craft", "lore"]), 15)
        return "The stranger stayed through the cold and showed you things you'd never seen."
    return "The stranger warmed themselves at your fire and went on their way."


def _send_on(ctx):
    return "You gave the stranger directions to the next camp, and nothing else."


def _sit_with_dying(ctx):
    _gain(ctx, "regard", 1)
    target = ctx.state.character(ctx.event.target_id) if ctx.event else None
    return f"You sat with {target.name} to the end." if target else "You kept the vigil."


def _ask_memory(ctx):
    advance(ctx.nation, "lore", 1.5)
    target = ctx.state.character(ctx.event.target_id) if ctx.event else None
    who = target.name if target else "them"
    return f"You sat with {who} and asked what they remembered, and kept every word."


def _search(ctx):
    return "You searched the hills from first light."


def _nurse_sick(ctx):
    for c in ctx.state.living():
        if c.settlement_id == ctx.char.settlement_id:
            heal(c, 3)
    _local(ctx, cohesion=1)
    ctx.state.modifiers["plague"] = ctx.state.modifiers.get("plague", 0) * 0.85
    return "You carried water and kept fires going for the sick."


def _help_camp(ctx):
    camp = _event_camp(ctx)
    _local(ctx, cohesion=2, camp=camp)
    for c in ctx.state.living():
        if c.settlement_id == camp.id:
            heal(c, 5)
    _gain(ctx, "regard", 1)
    return f"You helped {camp.name} bury its dead and build again."


# --- answers: danger from outside --------------------------------------------------


def _answer_raid(ctx):
    return "You sent word to the raiders that this could not go on."


def _avenge_raid(ctx):
    n = ctx.state.neighbour(ctx.event.data.get("neighbour")) if ctx.event else None
    if n is None:
        n = next((x for x in ctx.state.neighbours.values() if x.met), None)
    harm = discoveries.fx(ctx.state, "raid_mult")
    _gain(ctx, "regard", 3)
    if n is None:
        return "There was no one left to punish."
    n.relations = max(-1.0, n.relations - 0.35)
    n.population *= 1 - 0.04 * harm
    if ctx.rng.random() < 0.3:
        ctx.state.seat.population *= 0.98
        return f"Our people fell on the {n.name} by night. Not all of ours came back."
    return f"Our people fell on the {n.name} by night and took back more than was stolen."


def _stand_guard(ctx):
    camp = _event_camp(ctx)
    ctx.nation.watched_until = ctx.state.year + 1
    _local(ctx, cohesion=2, camp=camp)
    _gain(ctx, "regard", 2)
    return f"You and yours stood guard over {camp.name} through the dark months."


def _meet_challenge(ctx):
    n = ctx.state.neighbour(ctx.event.data.get("neighbour")) if ctx.event else None
    roll = ctx.rng.random()
    if roll < 0.55:
        _gain(ctx, "regard", 4)
        _people(ctx, cohesion=1)
        return "You met their champion at the border and bested him. The songs have it already."
    heal(ctx.char, -15)
    if n:
        n.relations = min(1.0, n.relations + 0.05)
    return "You met their champion and were carried home. They were gracious about it."


def _decline_challenge(ctx):
    n = ctx.state.neighbour(ctx.event.data.get("neighbour")) if ctx.event else None
    if n:
        n.relations = min(1.0, n.relations + 0.05)
    _local(ctx, cohesion=-0.5)
    return "You sent word that our people do not fight for sport. Some of the young were sorry."


def _hunt_beast(ctx):
    return "You went out after the beast."


def _guard_young(ctx):
    _local(ctx, cohesion=0.5)
    return "You kept the children close to the fires and never let them out of sight."


# --- answers: what each role meets -----------------------------------------------


def _share_evenly(ctx):
    ctx.nation.stores.add({"food": 6 * _richness(ctx, "animal")})
    _local(ctx, cohesion=1)
    _gain(ctx, "regard", 1)
    return "You cut the meat into equal shares, one for every fire."


def _best_cut(ctx):
    _gain(ctx, "food", 12 * _richness(ctx, "animal"))
    _local(ctx, cohesion=-0.5)
    return "You kept the best of the kill for your own fire."


def _feed_weak(ctx):
    for c in ctx.state.living():
        if c.settlement_id == ctx.char.settlement_id and c.health < 60:
            heal(c, 4)
    _local(ctx, cohesion=0.5)
    _gain(ctx, "regard", 1)
    return "The best of the meat went to the old and to mothers with babies at the breast."


def _teach_deep(ctx):
    advance(ctx.nation, "lore", 3)
    _gain(ctx, "regard", 1)
    return "You taught the young the oldest songs, the ones only a few still knew."


def _hold_secrets(ctx):
    _gain(ctx, "regard", 3)
    ctx.nation.lore = max(0.0, ctx.nation.lore - 1)
    return "Some songs, you decided, were not for everyone."


def _good_signs(ctx):
    _people(ctx, cohesion=1.5)
    _gain(ctx, "regard", 2)
    return "You told the people the signs were good, and they were glad to hear it."


def _true_signs(ctx):
    _gain(ctx, "regard", 1)
    return "You told the people you did not know what it meant. Some trusted you more for it."


def _make_for(ctx):
    who = _target(ctx)
    _local(ctx, plenty=1)
    _gain(ctx, "regard", 2)
    if who:
        who.adjust_affinity(ctx.char.id, 0.25)
        return f"You made {who.name} the best blade you could."
    return "You made the best blade you could, and gave it away."


def _ask_return(ctx):
    _gain(ctx, "food", 6)
    _gain(ctx, "regard", 0.5)
    return "You made the blade, and got a good share of meat for it."


def _fine_work(ctx):
    _gain(ctx, "regard", 1)
    heal(ctx.char, 2)
    return "You made something fine, and kept it."


def _fair_measure(ctx):
    _local(ctx, cohesion=1)
    _gain(ctx, "food", 6)
    _gain(ctx, "regard", 2)
    return "You gave fair measure, and they will remember it."


def _hard_bargain(ctx):
    for category in ("tokens", "wares"):
        if category in ctx.nation.names:
            _gain(ctx, category, 5)
    _gain(ctx, "food", 8)
    who = _target(ctx)
    if who:
        who.adjust_affinity(ctx.char.id, -0.15)
    return "You came out of the trade the better."


# --- what an answer needs ---------------------------------------------------------


def _failing(state):
    leader = state.leader
    return leader is None or (
        leader.age(state.year) >= STEP_ASIDE_AGE or leader.health < FRAIL_HEALTH
    )


def could_lead(state, char):
    return (
        char.station != "leader"
        and char.age(state.year) >= LEADER_AGE
        and char.means.get("regard") >= 25
        and state.nation.succession != "lineage"
    )


def _has_family(state, char):
    return bool(family_of(state, char))


def _has_food(amount):
    return lambda state, char: char.means.get("food") > amount


def _stores_have(amount):
    return lambda state, char: state.nation.stores.get("food") >= amount


def _has_leader(state, char):
    return state.leader is not None and state.leader.id != char.id


def _not_leading(state, char):
    return char.station != "leader"


ACTION_LIST = [
    # cares anyone can keep
    Action(
        "care_family",
        "Look after your kin",
        "Mend, provide and spend time with your family.",
        (),
        ("caring",),
        0.03,
        _care_family,
        {"hands": 2},
        requires=_has_family,
        care=True,
    ),
    Action(
        "sit_alone",
        "Sit alone with the unseen",
        "Spend the evenings apart, listening.",
        (),
        ("contemplative",),
        0.02,
        _sit_alone,
        care=True,
    ),
    Action(
        "rest",
        "Rest",
        "Let the year pass gently and recover your strength.",
        (),
        (),
        0.0,
        _rest,
        care=True,
    ),
    # each role's own cares
    Action(
        "go_among",
        "Go among the camps",
        "Visit every camp and hear what is on people's minds.",
        ("leader",),
        ("caring",),
        0.02,
        _go_among,
        {"hands": 2},
        care=True,
    ),
    Action(
        "sing_songs",
        "Sing the old songs",
        "Keep what the people know alive by teaching it.",
        ("keeper",),
        ("studious", "contemplative"),
        0.02,
        _sing_songs,
        {"hands": 2},
        care=True,
    ),
    Action(
        "tend_sick",
        "Tend the sick",
        "Go from shelter to shelter with herbs and songs.",
        ("keeper",),
        ("caring",),
        0.05,
        _tend_sick,
        {"hands": 2, "food": 2},
        care=True,
    ),
    Action(
        "hunt",
        "Hunt",
        "Go after game for your family.",
        ("hunter",),
        ("diligent",),
        0.01,
        _hunt,
        {"hands": 3},
        care=True,
    ),
    Action(
        "forage",
        "Forage",
        "Gather roots, seeds and fruit for your family.",
        ("gatherer",),
        ("diligent",),
        0.01,
        _forage,
        {"hands": 3},
        care=True,
    ),
    Action(
        "show_plants",
        "Show the young the plants",
        "Teach which plants feed and which kill.",
        ("gatherer", "planter"),
        ("caring", "studious"),
        0.03,
        _show_plants,
        {"hands": 2},
        care=True,
    ),
    Action(
        "make_tools",
        "Make tools for others",
        "Knap and shape for whoever needs it.",
        ("maker",),
        ("generous", "diligent"),
        0.03,
        _make_tools,
        {"hands": 3},
        care=True,
    ),
    Action(
        "fish",
        "Fish",
        "Work the water for your family.",
        ("fisher",),
        ("diligent",),
        0.01,
        _fish,
        {"hands": 3},
        care=True,
    ),
    Action(
        "tend_fields",
        "Tend your fields",
        "Plant, weed, guard and harvest.",
        ("planter",),
        ("diligent",),
        0.01,
        _tend_fields,
        {"hands": 4},
        care=True,
    ),
    Action(
        "help_neighbours",
        "Help your neighbours",
        "Lend your hands where they are short.",
        ("planter", "herder", "fisher"),
        ("generous", "caring"),
        0.04,
        _help_neighbours,
        {"hands": 3},
        care=True,
    ),
    Action(
        "tend_herd",
        "Tend your herd",
        "Move the beasts to good grazing and keep them safe.",
        ("herder",),
        ("diligent",),
        0.01,
        _tend_herd,
        {"hands": 3},
        care=True,
    ),
    Action(
        "trade",
        "Carry goods between families",
        "Find who has what, and who wants it.",
        ("trader",),
        ("diligent",),
        0.01,
        _trade,
        {"hands": 2},
        care=True,
    ),
    Action(
        "keep_watch",
        "Keep watch over the camps",
        "Walk the edges by night, so raiders find the people awake.",
        ("warrior",),
        ("diligent", "caring"),
        0.02,
        _keep_watch,
        {"hands": 3},
        care=True,
    ),
    Action(
        "train_young",
        "Train the young",
        "Teach the young to hold a line and loose together.",
        ("warrior",),
        ("diligent", "studious"),
        0.01,
        _train_young,
        {"hands": 2},
        care=True,
    ),
    # hunger
    Action(
        "open_stores",
        "Open the common stores",
        "Let whoever is hungry take from what is held in common.",
        ("leader",),
        ("generous",),
        0.05,
        _open_stores,
        {"food": 20},
        scope="people",
        requires=_stores_have(20),
    ),
    Action(
        "share_food",
        "Share your family's food",
        "Give some of what your family has to those who have little.",
        (),
        ("generous",),
        0.05,
        _share_food,
        {"food": 6},
        requires=_has_food(6),
    ),
    Action(
        "bring_food",
        "Bring them what you can get",
        "Work your hardest and carry it to the hungry.",
        FOOD_ROLES,
        ("generous", "diligent"),
        0.04,
        _bring_food,
        {"hands": 3},
    ),
    Action(
        "keep_close",
        "Keep your family's food close",
        "Hard times are coming. See to your own first.",
        (),
        ("acquisitive",),
        -0.03,
        _keep_close,
        {"hands": 1},
    ),
    # the common stores running low
    Action(
        "great_hunt",
        "Lead a great hunt",
        "Take the strongest hunters out for meat for everyone.",
        ("leader",),
        ("diligent", "ambitious"),
        0.0,
        _great_hunt,
        {"hands": 8},
        scope="people",
    ),
    Action(
        "stock_stores",
        "Bring food to the common stores",
        "Work for what is held in common, not only for your own.",
        FOOD_ROLES,
        ("generous", "diligent"),
        0.03,
        _stock_stores,
        {"hands": 3},
    ),
    # plenty
    Action(
        "feast_all",
        "Hold a feast for all the camps",
        "Bring everyone together while there is plenty.",
        ("leader",),
        ("generous", "indulgent"),
        0.02,
        _feast_all,
        {"food": 15},
        scope="people",
        requires=_stores_have(15),
    ),
    Action(
        "larger_share",
        "Take a larger share",
        "The leader's family deserves more.",
        ("leader",),
        ("acquisitive",),
        -0.05,
        _larger_share,
        requires=_stores_have(1),
    ),
    Action(
        "take_more",
        "Help yourself from the common stores",
        "There is plenty; no one will miss a little.",
        (),
        ("acquisitive",),
        -0.05,
        _take_more,
        requires=lambda state, char: _not_leading(state, char) and _stores_have(1)(state, char),
    ),
    Action(
        "feast",
        "Eat and make merry",
        "Enjoy what you have while you have it.",
        (),
        ("indulgent",),
        -0.01,
        _feast,
        {"food": 5},
    ),
    # quarrels
    Action(
        "call_together",
        "Call the people together",
        "Bring the camps together to talk and settle things.",
        ("leader",),
        ("caring",),
        0.02,
        _call_together,
        {"regard": 4},
    ),
    Action(
        "settle_quarrels",
        "Settle the quarrels",
        "Hear out every grievance and decide.",
        ("leader",),
        ("caring", "contemplative"),
        0.03,
        _settle_quarrels,
        {"regard": 2},
    ),
    Action(
        "drive_out",
        "Drive out a troublemaker",
        "Someone stirs up trouble. Be rid of them.",
        ("leader",),
        ("harsh",),
        -0.06,
        _drive_out,
        {"regard": 3},
    ),
    Action(
        "speak_at_fires",
        "Speak for patience at the fires",
        "Go from fire to fire and cool tempers.",
        (),
        ("caring",),
        0.03,
        _speak_at_fires,
        {"hands": 1},
        requires=_not_leading,
    ),
    Action(
        "judge_feud",
        "Judge between them",
        "Hear both families and decide what is owed.",
        ("leader",),
        ("contemplative", "caring"),
        0.04,
        _judge_feud,
        {"regard": 3},
    ),
    Action(
        "make_peace",
        "Go between them",
        "Carry words between the families before blood is spilled.",
        (),
        ("generous", "caring"),
        0.04,
        _make_peace,
        {"regard": 2},
        requires=_not_leading,
    ),
    Action(
        "side_with",
        "Side with the {a} family",
        "They were wronged, and others should hear it.",
        (),
        ("ambitious", "harsh"),
        -0.03,
        _side_with,
    ),
    # who leads
    Action(
        "stand_forward",
        "Ask the people to follow you",
        "Stand up at the gathering and offer to lead. Not everyone will thank you for it.",
        (),
        ("ambitious",),
        -0.01,
        _stand_forward,
        {"regard": 3},
        requires=could_lead,
    ),
    Action(
        "back_leader",
        "Stand behind {leader}",
        "Tell the people to keep faith with the one who leads them.",
        (),
        ("generous", "caring"),
        0.02,
        _back_leader,
        {"regard": 2},
        requires=_has_leader,
    ),
    Action(
        "back_rival",
        "Speak for {rival}",
        "Say at the fires that it is time for someone else to lead.",
        (),
        ("ambitious",),
        -0.01,
        _back_rival,
        {"regard": 1},
        requires=_not_leading,
    ),
    Action(
        "stay_out",
        "Keep out of it",
        "Let them settle it between themselves.",
        (),
        ("contemplative",),
        0.0,
        _stay_out,
    ),
    Action(
        "win_over",
        "Win {rival} over",
        "Sit with them, give gifts, and listen until they are with you.",
        ("leader",),
        ("generous", "caring"),
        0.03,
        _win_over,
        {"food": 6},
        requires=_has_food(6),
    ),
    Action(
        "make_room",
        "Give {rival} a place beside you",
        "Let them be heard first; the people are better led by two who agree.",
        ("leader",),
        ("caring", "contemplative"),
        0.04,
        _make_room,
        {"regard": 2},
    ),
    Action(
        "face_down",
        "Face {rival} down before everyone",
        "Make them say it to your face at the gathering, and answer them.",
        ("leader",),
        ("harsh", "ambitious"),
        -0.04,
        _face_down,
        {"regard": 3},
    ),
    # those near you
    Action(
        "shame_idler",
        "Shame them before everyone",
        "Make an example of someone who does not pull their weight.",
        (),
        ("harsh",),
        -0.05,
        _shame_idler,
    ),
    Action(
        "find_work",
        "Find them work they can do",
        "Perhaps no one has shown them how.",
        (),
        ("caring", "generous"),
        0.03,
        _find_work,
        {"hands": 1},
    ),
    Action(
        "tend_relative",
        "Tend them",
        "Stay by their side and nurse them.",
        (),
        ("caring",),
        0.05,
        _tend_relative,
        {"hands": 2, "food": 2},
    ),
    Action(
        "welcome_stranger",
        "Take the stranger in",
        "Share your fire and food.",
        (),
        ("generous",),
        0.04,
        _welcome_stranger,
        {"food": 4},
    ),
    Action(
        "send_on",
        "Send them on their way",
        "Point them to the next camp. Your food is for your own.",
        (),
        ("acquisitive",),
        -0.02,
        _send_on,
    ),
    Action(
        "sit_with_dying",
        "Sit with them",
        "Keep them company to the end.",
        (),
        ("caring", "contemplative"),
        0.04,
        _sit_with_dying,
    ),
    Action(
        "ask_memory",
        "Ask what they remember",
        "Sit with them, and keep what they know from dying with them.",
        (),
        ("studious", "caring"),
        0.03,
        _ask_memory,
    ),
    Action(
        "search",
        "Join the search",
        "Go out and look.",
        (),
        ("caring",),
        0.05,
        _search,
        {"hands": 3},
    ),
    Action(
        "nurse_sick",
        "Nurse the sick",
        "Carry water, keep fires going, sit with the feverish.",
        (),
        ("caring",),
        0.05,
        _nurse_sick,
        {"hands": 2},
    ),
    Action(
        "help_camp",
        "Help {camp} build again",
        "Go and lend your hands where they were struck.",
        (),
        ("caring", "generous"),
        0.04,
        _help_camp,
        {"hands": 3},
    ),
    # danger from outside
    Action(
        "answer_raid",
        "Seek redress",
        "Go to the raiders and demand it stop, without more blood.",
        ("leader",),
        ("contemplative", "caring"),
        0.02,
        _answer_raid,
        {"regard": 3},
    ),
    Action(
        "avenge_raid",
        "Avenge the raid",
        "Lead our people against the raiders.",
        ("leader", "hunter", "warrior"),
        ("harsh", "ambitious"),
        -0.08,
        _avenge_raid,
        {"hands": 6},
        scope="people",
    ),
    Action(
        "stand_guard",
        "Stand guard over {camp}",
        "Keep your band at the struck camp until the raiders give up.",
        ("warrior",),
        ("diligent", "caring"),
        0.03,
        _stand_guard,
        {"hands": 4},
    ),
    Action(
        "meet_challenge",
        "Meet their champion",
        "Go to the border and fight, for the honour of the people.",
        ("warrior", "hunter"),
        ("ambitious",),
        -0.01,
        _meet_challenge,
        {"hands": 2},
    ),
    Action(
        "decline_challenge",
        "Send word that we do not fight for sport",
        "Let their champion go home unmet.",
        ("warrior", "hunter", "leader"),
        ("contemplative",),
        0.02,
        _decline_challenge,
    ),
    Action(
        "hunt_beast",
        "Hunt the beast down",
        "Go after it before it takes anyone else.",
        ("leader", "hunter", "warrior"),
        ("diligent", "caring"),
        0.03,
        _hunt_beast,
        {"hands": 4},
    ),
    Action(
        "guard_young",
        "Keep the children close",
        "Watch the little ones and keep them near the fires.",
        (),
        ("caring",),
        0.02,
        _guard_young,
        {"hands": 1},
    ),
    # what each role meets
    Action(
        "share_evenly",
        "Share it out evenly",
        "An equal share for every fire.",
        ("hunter",),
        ("generous",),
        0.04,
        _share_evenly,
        {"hands": 2},
    ),
    Action(
        "best_cut",
        "Keep the best of it",
        "You did the work; you eat first.",
        ("hunter",),
        ("acquisitive",),
        -0.03,
        _best_cut,
        {"hands": 2},
    ),
    Action(
        "feed_weak",
        "Give the best to the old and the nursing",
        "Those who need it most should have it.",
        ("hunter",),
        ("caring",),
        0.04,
        _feed_weak,
        {"hands": 2},
    ),
    Action(
        "teach_deep",
        "Teach them",
        "The oldest songs belong to everyone who will carry them.",
        ("keeper",),
        ("studious", "generous"),
        0.03,
        _teach_deep,
        {"hands": 2},
    ),
    Action(
        "hold_secrets",
        "Keep the deepest songs to yourself",
        "Knowledge is worth more when few have it.",
        ("keeper",),
        ("acquisitive", "ambitious"),
        -0.03,
        _hold_secrets,
    ),
    Action(
        "good_signs",
        "Tell them the signs are good",
        "The people need hope more than they need the truth.",
        ("keeper", "leader"),
        ("ambitious",),
        -0.01,
        _good_signs,
    ),
    Action(
        "true_signs",
        "Tell them you do not know",
        "Say only what you see.",
        ("keeper", "leader"),
        ("contemplative",),
        0.02,
        _true_signs,
    ),
    Action(
        "make_for",
        "Make it for them",
        "Your best work, given freely.",
        ("maker",),
        ("generous", "diligent"),
        0.03,
        _make_for,
        {"hands": 2},
    ),
    Action(
        "ask_return",
        "Ask something in return",
        "Good work deserves a share of meat.",
        ("maker",),
        ("diligent",),
        0.0,
        _ask_return,
        {"hands": 2},
    ),
    Action(
        "fine_work",
        "Make something fine for yourself instead",
        "Take your time over something beautiful, and keep it.",
        ("maker",),
        ("indulgent",),
        -0.01,
        _fine_work,
        {"hands": 2},
    ),
    Action(
        "fair_measure",
        "Give fair measure",
        "Trade as you would want to be traded with.",
        ("trader",),
        ("generous",),
        0.03,
        _fair_measure,
        {"hands": 1},
    ),
    Action(
        "hard_bargain",
        "Drive a hard bargain",
        "They need it more than you do. Make them pay for it.",
        ("trader",),
        ("acquisitive",),
        -0.04,
        _hard_bargain,
        {"hands": 1},
    ),
]

ACTIONS = {a.id: a for a in ACTION_LIST}


def cares_for(state, char):
    """The lasting cares open to this character this year."""
    return [a for a in ACTION_LIST if a.care and open_to(state, char, a)]
