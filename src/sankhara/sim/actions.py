"""One-year deeds: what a character can do with a slot of attention this year.

Every role has its own deeds with a different reach: the leader's draw on the
people's common stores and touch everyone; the others draw on their own family's
means and touch those nearby. Each deed carries inclination tags and a hidden
karma value reflecting the intention behind it, never its outcome.

Longer undertakings are projects (`projects.py`). Effects receive a Ctx and return
a short sentence for the chronicle.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from sankhara.sim import discoveries, tendencies
from sankhara.sim.nation import adjust_settlements, advance, clamp, land_richness, people_scale
from sankhara.sim.people import family_of
from sankhara.sim.stations import ADULT_AGE


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
    name: str
    text: str
    stations: tuple  # empty = open to every role
    tags: tuple
    karma: float  # hidden: the intention, not the outcome
    effect: Callable = field(repr=False)
    cost: dict = field(default_factory=dict)
    scope: str = "own"  # "people" spends the common stores when the leader acts
    requires: Callable | None = field(default=None, repr=False)
    obligation_only: bool = False


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
    return {k: max(1, round(v * mult)) for k, v in item.cost.items()}


# --- helpers ---------------------------------------------------------------


def _family(ctx):
    return [c for _, c in family_of(ctx.state, ctx.char)]


def _local(ctx, cohesion=0.0, plenty=0.0):
    adjust_settlements(ctx.state, cohesion=cohesion, plenty=plenty, only=ctx.settlement.id)


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


def _richness(ctx, land):
    return land_richness(ctx.state, ctx.settlement, land) * ctx.state.modifiers.get("harvest", 1.0)


def _gain(ctx, category, amount):
    ctx.char.means.add({category: amount})


def _young_children(state, char):
    return [
        c
        for cid in char.children
        if (c := state.character(cid)) and c.alive and c.age(state.year) < ADULT_AGE
    ]


def _nudge_insight(ctx, domain, amount):
    options = [d for d in discoveries.available(ctx.state) if d.domain == domain]
    if options:
        discoveries.add_insight(ctx.state, ctx.rng.choice(options).id, amount)


# --- for anyone --------------------------------------------------------------


def _care_family(ctx):
    for c in _family(ctx):
        heal(c, 5)
        c.adjust_affinity(ctx.char.id, 0.1)
        ctx.char.adjust_affinity(c.id, 0.05)
    return "Your family was looked after."


def _rest(ctx):
    heal(ctx.char, 10)
    return "You rested and recovered some strength."


def _share_food(ctx):
    _local(ctx, cohesion=1.5)
    _gain(ctx, "regard", 1)
    who = neighbour(ctx)
    if who:
        who.adjust_affinity(ctx.char.id, 0.15)
        heal(who, 5)
    return "Those with little ate a little better."


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


def _boast(ctx):
    _gain(ctx, "regard", 3)
    who = neighbour(ctx)
    if who:
        who.adjust_affinity(ctx.char.id, -0.1)
    return "People heard a great deal about you this year."


def _sit_alone(ctx):
    heal(ctx.char, 4)
    _nudge_insight(ctx, "lore", 2)
    return "You spent long evenings alone at the edge of the camp, listening."


def _shame_idler(ctx):
    who = neighbour(ctx)
    _gain(ctx, "regard", 2)
    if who:
        who.adjust_affinity(ctx.char.id, -0.3)
        heal(who, -3)
        return f"{who.name} was shamed before everyone. Some laughed."
    return "There was no one to make an example of."


def _teach_child(ctx):
    kids = _young_children(ctx.state, ctx.char)
    for kid in kids:
        tendencies.pull_toward(kid.tendencies, ctx.char.tendencies, 0.15)
        kid.adjust_affinity(ctx.char.id, 0.1)
    return "Your children followed you everywhere, watching how you did things."


# --- the leader --------------------------------------------------------------


def _call_together(ctx):
    _people(ctx, cohesion=3)
    return "The camps came together; old grudges were aired and some were settled."


def _open_stores(ctx):
    relief = 20 * people_scale(ctx.state)
    ctx.state.modifiers["relief"] = ctx.state.modifiers.get("relief", 0.0) + relief
    _people(ctx, cohesion=1.5)
    return "The common stores were opened to whoever needed them."


def _great_hunt(ctx):
    food = 15 * _richness(ctx, "animal") * people_scale(ctx.state)
    ctx.nation.stores.add({"food": food})
    _gain(ctx, "regard", 2)
    if ctx.rng.random() < 0.08:
        heal(ctx.char, -15)
        return "The great hunt brought meat for all, but you were gored."
    return "The great hunt brought meat for all."


def _larger_share(ctx):
    taken = min(14.0, ctx.nation.stores.get("food"))
    ctx.nation.stores.add({"food": -taken})
    _gain(ctx, "food", taken)
    _people(ctx, cohesion=-2)
    return "Your family's share grew. People noticed."


def _drive_out(ctx):
    if ctx.rng.random() < 0.6:
        _people(ctx, cohesion=2)
        return "A troublemaker was driven from the camp. It was quieter afterwards."
    _people(ctx, cohesion=-2)
    return "A troublemaker was driven out. His kin have not forgiven it."


def _settle_quarrels(ctx):
    _people(ctx, cohesion=4)
    _gain(ctx, "regard", 1)
    return "You heard out every side, and most went away content."


# --- keepers -----------------------------------------------------------------


def _sing_songs(ctx):
    advance(ctx.nation, "lore", 2.5)
    return "The old songs were sung through the long nights, and the young learned them."


def _tend_sick(ctx):
    near = [c for c in ctx.state.living() if c.settlement_id == ctx.char.settlement_id]
    for c in near:
        heal(c, 4)
    _local(ctx, cohesion=1)
    ctx.state.modifiers["plague"] = ctx.state.modifiers.get("plague", 0) * 0.8
    return "You went from shelter to shelter with your herbs and your songs."


def _read_omens(ctx):
    _gain(ctx, "regard", 2)
    if ctx.rng.random() < 0.6:
        _people(ctx, cohesion=1.5)
        return "The signs were good, and the people were glad to hear it."
    _people(ctx, cohesion=-1.5)
    return "The signs were dark. The people grew uneasy."


def _hold_secrets(ctx):
    _gain(ctx, "regard", 3)
    ctx.nation.lore = max(0.0, ctx.nation.lore - 1)
    return "Some songs, you decided, were not for everyone."


# --- hunters, gatherers, makers and the rest --------------------------------


def _hunt(ctx):
    _gain(ctx, "food", 8 * _richness(ctx, "animal"))
    if ctx.rng.random() < 0.05:
        heal(ctx.char, -12)
        return "You hunted well, but came back torn by a beast."
    return "You hunted and brought meat home."


def _share_kill(ctx):
    ctx.nation.stores.add({"food": 8 * _richness(ctx, "animal")})
    _gain(ctx, "regard", 2)
    return "You brought your kill back for the whole camp."


def _best_cut(ctx):
    _gain(ctx, "food", 12 * _richness(ctx, "animal"))
    _local(ctx, cohesion=-0.5)
    return "You kept the best of every kill for your own fire."


def _forage(ctx):
    _gain(ctx, "food", 8 * _richness(ctx, "plant"))
    return "You knew where to look, and came home laden."


def _show_plants(ctx):
    _nudge_insight(ctx, "land", 4)
    advance(ctx.nation, "lore", 0.5)
    return "The children learned which plants feed and which kill."


def _make_tools(ctx):
    _gain(ctx, "regard", 3)
    _local(ctx, plenty=1.5)
    return "Your blades and scrapers went to whoever needed them."


def _fine_work(ctx):
    _gain(ctx, "regard", 1)
    heal(ctx.char, 2)
    return "You made something fine, and kept it."


def _fish(ctx):
    _gain(ctx, "food", 9 * _richness(ctx, "water"))
    return "The water was generous."


def _tend_fields(ctx):
    _gain(ctx, "food", 11 * _richness(ctx, "plant"))
    return "You worked your ground from planting to harvest."


def _help_neighbours(ctx):
    who = neighbour(ctx)
    _local(ctx, cohesion=1.5)
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


def _hard_bargain(ctx):
    for category in ("tokens", "wares"):
        if category in ctx.nation.names:
            _gain(ctx, category, 5)
    who = neighbour(ctx)
    if who:
        who.adjust_affinity(ctx.char.id, -0.15)
    return "You came out of every trade the better."


# --- answering what's expected -------------------------------------------------


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


def _sit_with_dying(ctx):
    _gain(ctx, "regard", 1)
    target = ctx.state.character(ctx.event.target_id) if ctx.event else None
    return f"You sat with {target.name} to the end." if target else "You kept the vigil."


def _search(ctx):
    return "You searched the hills from first light."


def _judge_feud(ctx):
    _gain(ctx, "regard", 1)
    return "You heard both families out."


def _make_peace(ctx):
    return "You went between the two families, carrying words."


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


def _hunt_beast(ctx):
    return "You went out after the beast."


def _has_family(state, char):
    return bool(family_of(state, char))


def _has_young(state, char):
    return bool(_young_children(state, char))


def _stores_have(amount):
    return lambda state, char: state.nation.stores.get("food") >= amount


def _raided(state, char):
    return any(e.kind == "raid" for e in state.events)


ACTION_LIST = [
    # anyone
    Action(
        "care_family",
        "Look after your family",
        "Mend, provide and spend time with your kin.",
        (),
        ("caring",),
        0.03,
        _care_family,
        {"hands": 2},
        requires=_has_family,
    ),
    Action(
        "rest",
        "Rest",
        "Let the year pass gently and recover your strength.",
        (),
        (),
        0.0,
        _rest,
    ),
    Action(
        "share_food",
        "Share your food",
        "Give some of what your family has to those who have little.",
        (),
        ("generous",),
        0.05,
        _share_food,
        {"food": 6},
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
    Action(
        "take_more",
        "Take more than your share",
        "Help yourself from the common stores.",
        (),
        ("acquisitive",),
        -0.05,
        _take_more,
        requires=_stores_have(1),
    ),
    Action(
        "boast",
        "Make your worth known",
        "Make sure everyone hears what you have done.",
        (),
        ("ambitious",),
        -0.01,
        _boast,
        {"hands": 1},
    ),
    Action(
        "sit_alone",
        "Sit alone with the unseen",
        "Spend the evenings apart, listening.",
        (),
        ("contemplative",),
        0.02,
        _sit_alone,
    ),
    Action(
        "shame_idler",
        "Shame an idler",
        "Make an example of someone who does not pull their weight.",
        (),
        ("harsh",),
        -0.05,
        _shame_idler,
    ),
    Action(
        "teach_child",
        "Teach your children",
        "Keep your young ones by you and show them how things are done.",
        (),
        ("caring", "studious"),
        0.03,
        _teach_child,
        {"hands": 1},
        requires=_has_young,
    ),
    # the leader
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
        "open_stores",
        "Open the common stores",
        "Let whoever is hungry take from what is held in common.",
        ("leader",),
        ("generous",),
        0.05,
        _open_stores,
        {"food": 20},
        scope="people",
    ),
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
        "settle_quarrels",
        "Settle quarrels",
        "Hear out every grievance and decide.",
        ("leader",),
        ("caring", "contemplative"),
        0.03,
        _settle_quarrels,
        {"regard": 2},
    ),
    # keepers
    Action(
        "sing_songs",
        "Sing the old songs",
        "Keep what the people know alive by teaching it.",
        ("keeper",),
        ("studious", "contemplative"),
        0.02,
        _sing_songs,
        {"hands": 2},
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
    ),
    Action(
        "read_omens",
        "Read the omens",
        "Tell the people what the signs say.",
        ("keeper",),
        ("contemplative", "ambitious"),
        0.0,
        _read_omens,
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
    # hunters
    Action(
        "hunt",
        "Hunt",
        "Go after game for your family.",
        ("hunter",),
        ("diligent",),
        0.01,
        _hunt,
        {"hands": 3},
    ),
    Action(
        "share_kill",
        "Share the kill",
        "Bring what you kill back for the whole camp.",
        ("hunter",),
        ("generous",),
        0.04,
        _share_kill,
        {"hands": 3},
    ),
    Action(
        "best_cut",
        "Keep the best of the kill",
        "You did the work; you eat first.",
        ("hunter",),
        ("acquisitive",),
        -0.03,
        _best_cut,
        {"hands": 3},
    ),
    # gatherers
    Action(
        "forage",
        "Forage",
        "Gather roots, seeds and fruit for your family.",
        ("gatherer",),
        ("diligent",),
        0.01,
        _forage,
        {"hands": 3},
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
    ),
    # makers
    Action(
        "make_tools",
        "Make tools for others",
        "Knap and shape for whoever needs it.",
        ("maker",),
        ("generous", "diligent"),
        0.03,
        _make_tools,
        {"hands": 3},
    ),
    Action(
        "fine_work",
        "Make something fine for yourself",
        "Take your time over something beautiful.",
        ("maker",),
        ("indulgent",),
        -0.01,
        _fine_work,
        {"hands": 3},
    ),
    # roles that come later
    Action(
        "fish",
        "Fish",
        "Work the water for your family.",
        ("fisher",),
        ("diligent",),
        0.01,
        _fish,
        {"hands": 3},
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
    ),
    Action(
        "hard_bargain",
        "Drive hard bargains",
        "Make sure every trade favours you.",
        ("trader",),
        ("acquisitive",),
        -0.04,
        _hard_bargain,
        {"hands": 2},
    ),
    # what events ask of people
    Action(
        "tend_relative",
        "Tend them",
        "Stay by their side and nurse them.",
        (),
        ("caring",),
        0.05,
        _tend_relative,
        {"hands": 2, "food": 2},
        obligation_only=True,
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
        obligation_only=True,
    ),
    Action(
        "sit_with_dying",
        "Sit with them",
        "Keep them company to the end.",
        (),
        ("caring", "contemplative"),
        0.04,
        _sit_with_dying,
        obligation_only=True,
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
        obligation_only=True,
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
        obligation_only=True,
    ),
    Action(
        "make_peace",
        "Make peace between them",
        "Go between the families before blood is spilled.",
        (),
        ("generous", "caring"),
        0.04,
        _make_peace,
        {"regard": 2},
        obligation_only=True,
    ),
    Action(
        "answer_raid",
        "Seek redress",
        "Go to the raiders and demand it stop, without more blood.",
        ("leader",),
        ("contemplative", "caring"),
        0.02,
        _answer_raid,
        {"regard": 3},
        obligation_only=True,
    ),
    Action(
        "avenge_raid",
        "Avenge the raid",
        "Lead our people against the raiders.",
        ("leader", "hunter"),
        ("harsh", "ambitious"),
        -0.08,
        _avenge_raid,
        {"hands": 6},
        scope="people",
        requires=_raided,
    ),
    Action(
        "hunt_beast",
        "Hunt the beast down",
        "Go after it before it takes anyone else.",
        ("leader", "hunter"),
        ("diligent", "caring"),
        0.03,
        _hunt_beast,
        {"hands": 4},
        obligation_only=True,
    ),
]

ACTIONS = {a.id: a for a in ACTION_LIST}


def actions_for(state, char):
    """The deeds open to this character this year (not counting obligations)."""
    return [
        a
        for a in ACTION_LIST
        if not a.obligation_only
        and (not a.stations or char.station in a.stations)
        and (a.requires is None or a.requires(state, char))
    ]
