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

from sankhara.sim import discoveries, say, tendencies
from sankhara.sim.nation import adjust_settlements, advance, clamp, land_richness, people_scale
from sankhara.sim.people import (
    LEADER_AGE,
    bid_to_lead,
    create_character,
    die,
    faction,
    family_of,
    grudge_key,
    members,
    standing,
    wed,
)
from sankhara.sim.peoples import WALL_YEARS
from sankhara.sim.stations import ADULT_AGE, BAND_ROLES, STATIONS

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
TALE_COST = 0.8  # what is left of someone's standing after tales are spread about them
BRIDE_PRICE = 10
CAPTIVES = 3
STOLEN = 15  # food taken from another family's unguarded stores
FIGHT_STARTS_FEUD = 0.25
AFFAIR_FOUND_OUT = 0.3
KILLING_FOUND_OUT = 0.5
NEWCOMERS = 5  # people in a family that comes to settle
FOUND_OUT = 0.35  # chance a wrong done in secret comes out
HEARD_OUT = 0.15  # how much a rival's followers warm to a leader who comes to hear them
STOOD_DOWN = 0.25  # how much a rival's followers cool toward one who stands down
MARRIAGE_STANDING = 10  # standing needed to be heard offering a marriage between families
LOAN = 10  # food lent to a neighbour until the harvests have turned
LOAN_YEARS = 2
FOR_MORE = 1.5  # what is asked back for a loan made for more
GIFT_FOR_MARKS = 8  # what a family gives to have its claim set down
WALL_FOOD = 6
SHARE = 6  # a family's share due at the leader's store
SURPLUS = 15  # the year's shares beyond what the people need, before their size


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


def _match_of(ctx):
    """The one offered, made known now if they were not before."""
    if ctx.event is None:
        return None
    if ctx.event.target_id is None:
        data, me = ctx.event.data, ctx.char
        who = create_character(
            ctx.state,
            rng_role(ctx),
            me.settlement_id,
            ctx.state.year - data.get("age", me.age(ctx.state.year)),
            gender="female" if me.gender == "male" else "male",
            family_name=data.get("family"),
        )
        who.name = data.get("match", who.name)
        ctx.event.target_id = who.id
        return who
    who = ctx.state.character(ctx.event.target_id)
    return who if who and who.alive and who.spouse_id is None else None


def rng_role(ctx):
    roles = [r for r in BAND_ROLES if r != "keeper"]
    return ctx.rng.choice(roles)


def _accept_match(ctx):
    match = _match_of(ctx)
    if match is None or ctx.char.spouse_id is not None:
        return "The match came to nothing."
    family = match.family_name
    for c in members(ctx.state, family):
        c.adjust_affinity(ctx.char.id, 0.1)
    wed(ctx.state, ctx.char, match)
    return f"You took {match.name} of the {family} family as your mate, and both families feasted."


def _refuse_match(ctx):
    data = ctx.event.data if ctx.event else {}
    family = data.get("family", "")
    for c in members(ctx.state, family) if family else []:
        c.adjust_affinity(ctx.char.id, -0.15)
    return f"You turned the {family} family's offer away. They took it ill."


def _kin_family(ctx):
    return ctx.event.data.get("family", "") if ctx.event else ""


def _share_with_kin(ctx):
    family = _kin_family(ctx)
    for c in members(ctx.state, family):
        c.adjust_affinity(ctx.char.id, 0.2)
        c.means.add({"food": 2})
    return f"You sent food to the {family} family. Kin look after kin."


def _refuse_kin(ctx):
    family = _kin_family(ctx)
    for c in members(ctx.state, family):
        c.adjust_affinity(ctx.char.id, -0.2)
    return f"You told the {family} family you had nothing to spare."


def _join_families(ctx):
    data = ctx.event.data if ctx.event else {}
    for name in (data.get("a"), data.get("b")):
        for c in members(ctx.state, name) if name else []:
            c.adjust_affinity(ctx.char.id, 0.15)
    return "You went between the two families with gifts, and spoke of a marriage."


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
    """Who the matter is about, or, for a deed done without one, whoever the people are
    divided over."""
    rid = ctx.event.target_id if ctx.event else ctx.state.nation.divided
    who = ctx.state.character(rid) if rid else None
    return who if who and who.alive else None


def _hear_them_out(ctx):
    r = _rival_of(ctx)
    if r is None:
        return "There was no one to hear out."
    leader = ctx.state.leader
    for c in faction(ctx.state, r, leader) if leader else []:
        if c.settlement_id == r.settlement_id:
            c.adjust_affinity(ctx.char.id, HEARD_OUT)
    _people(ctx, cohesion=1)
    adjust_settlements(ctx.state, cohesion=2, only=r.settlement_id)
    camp = ctx.state.settlement(r.settlement_id)
    where = camp.name if camp else "their camp"
    return f"You went to {where} and sat at {r.name}'s fire, and heard out all who came."


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
    if bid_to_lead(ctx.state, ctx.char, ctx.rng):
        return "You stood before the people and asked them to follow you, and they did."
    return "You stood before the people and asked them to follow you. Few did."


def _back_leader(ctx):
    leader = ctx.state.leader
    _people(ctx, cohesion=1)
    _gain(ctx, "regard", 1)
    r = _rival_of(ctx)
    if r is ctx.char and leader is not None:
        # the rival stands down: those who would have followed them turn back
        for c in faction(ctx.state, r, leader):
            c.adjust_affinity(r.id, -STOOD_DOWN)
        leader.adjust_affinity(r.id, 0.3)
        return f"You told the people you would not stand against {leader.name}."
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


def _speak_for_stranger(ctx):
    return "You said the stranger should be taken in, to anyone deciding."


def _speak_against_stranger(ctx):
    return "You said the stranger should be sent on, to anyone deciding."


def _take_in_family(ctx):
    camp = _event_camp(ctx)
    camp.population += NEWCOMERS
    _local(ctx, cohesion=-0.5, camp=camp)
    if ctx.rng.random() < 0.35:
        _nudge_insight(ctx, ctx.rng.choice(["land", "craft", "lore"]), 15)
    return f"The newcomers built their shelters at the edge of {camp.name}."


def _turn_away_family(ctx):
    who = ctx.event.data.get("people") if ctx.event else None
    for n in ctx.state.neighbours.values():
        if n.name == who:
            n.relations = max(-1.0, n.relations - 0.05)
    return "You told the newcomers there was no room for them."


# --- answers: what is yours, and what is theirs -----------------------------------


def _family_of_matter(ctx):
    return ctx.event.data.get("family", "") if ctx.event else ""


def _found_out(ctx, chance, what, family=None, cool=0.4, kept=0.85):
    """A wrong done in secret may come out: the wronged family cools toward the one who
    did it, a grudge begins between the families, and standing falls (to `kept` of what
    it was). Returns a line to add, or ''."""
    if ctx.rng.random() >= chance:
        return ""
    family = family if family is not None else _family_of_matter(ctx)
    for c in members(ctx.state, family):
        c.adjust_affinity(ctx.char.id, -cool)
    ctx.char.means.set("regard", ctx.char.means.get("regard") * kept)
    if family and family != ctx.char.family_name:
        ctx.state.nation.grudges[grudge_key(family, ctx.char.family_name)] = ctx.state.year
    return f" The {family} family found out about {what}, and will not forget it."


# --- answers: temptations ------------------------------------------------------------


def _spread_tale(ctx):
    who = _target(ctx)
    if who is None:
        return "There was no one to speak against."
    who.means.set("regard", who.means.get("regard") * TALE_COST)
    return f"You let it be known, quietly, what {who.name} is really like." + _found_out(
        ctx, 0.35, "your tales", kept=0.8
    )


def _praise_them(ctx):
    who = _target(ctx)
    if who:
        who.adjust_affinity(ctx.char.id, 0.2)
        who.means.add({"regard": 1})
    return "You spoke well of them, and meant most of it."


def _say_nothing(ctx):
    return "You kept your thoughts to yourself."


def _short_measure(ctx):
    _gain(ctx, "food", 10)
    return "You gave less than you took, and they never counted." + _found_out(
        ctx, 0.35, "the short measure"
    )


def _fair_trade(ctx):
    _gain(ctx, "food", 4)
    _warm_family(ctx, 0.1)
    return "You traded fairly, and both went home content."


def _bride_price(ctx):
    match = _match_of(ctx)
    if match is None or ctx.char.spouse_id is not None:
        return "The match came to nothing."
    family = match.family_name
    if ctx.char.gender == "female":
        _gain(ctx, "food", BRIDE_PRICE)
        line = f"The {family} family paid what was asked for you, and you went to {match.name}."
    else:
        paid = min(BRIDE_PRICE, ctx.char.means.get("food"))
        _gain(ctx, "food", -paid)
        for c in members(ctx.state, family):
            c.adjust_affinity(ctx.char.id, 0.15)
        line = f"You paid the {family} family for {match.name}, as is done."
    wed(ctx.state, ctx.char, match)
    return line


def _take_captives(ctx):
    n = ctx.state.neighbour(ctx.event.data.get("neighbour")) if ctx.event else None
    if n is None:
        return "There was no one to take."
    n.relations = max(-1.0, n.relations - 0.3)
    camp = ctx.settlement
    camp.population += CAPTIVES
    ctx.state.nation.stores.add({"food": 4 * CAPTIVES})
    _gain(ctx, "regard", 2)
    return f"You came back from the {n.name} with captives, to work in {camp.name} as yours."


def _set_blood_price(ctx):
    _gain(ctx, "regard", 1)
    return "You set what the wrong was worth, to be paid in food and goods."


def _ordeal(ctx):
    _gain(ctx, "regard", 1)
    return "You put them to the ordeal, and let the unseen show who was in the right."


def _keep_seed(ctx):
    ctx.state.nation.seed_kept = ctx.state.year
    _local(ctx, cohesion=-1.5)
    for c in ctx.state.living():
        if c.settlement_id == ctx.char.settlement_id and c.health < 50:
            heal(c, -3)
    return "You kept the seed back for planting, and the hungry went on being hungry."


# --- answers: what grows with later ideas ------------------------------------------


def _lend(ctx, back, line):
    who = _target(ctx)
    if who is None or ctx.char.means.get("food") < LOAN:
        return "You had nothing to lend."
    _gain(ctx, "food", -LOAN)
    who.means.add({"food": LOAN})
    ctx.state.nation.debts.append(
        {
            "by": who.id,
            "to": ctx.char.id,
            "food": round(LOAN * back),
            "due": ctx.state.year + LOAN_YEARS,
        }
    )
    return line.format(name=who.name)


def _lend_food(ctx):
    _warm_family(ctx, 0.1)
    return _lend(ctx, 1.0, "You lent {name} what they asked, to be given back in time.")


def _lend_for_more(ctx):
    return _lend(ctx, FOR_MORE, "You lent {name} what they asked, for more to be given back.")


def _give_outright(ctx):
    who = _target(ctx)
    if who is None or ctx.char.means.get("food") < LOAN:
        return "You had nothing to give."
    _gain(ctx, "food", -LOAN)
    who.means.add({"food": LOAN})
    _warm_family(ctx, 0.2)
    _gain(ctx, "regard", 1)
    return f"You gave {who.name} what they asked, and wanted nothing back."


def _refuse_loan(ctx):
    who = _target(ctx)
    if who:
        who.adjust_affinity(ctx.char.id, -0.1)
    return "You kept what you had."


def _debt(ctx):
    """The debt the matter is about, if it is still owed."""
    data = ctx.event.data if ctx.event else {}
    return next(
        (d for d in ctx.state.nation.debts if d["by"] == data.get("by") and d["to"] == ctx.char.id),
        None,
    )


def _settled(ctx, debt):
    ctx.state.nation.debts.remove(debt)


def _forgive_debt(ctx):
    debt = _debt(ctx)
    if debt is None:
        return "There was nothing left owed."
    _settled(ctx, debt)
    _warm_family(ctx, 0.25)
    _gain(ctx, "regard", 1)
    return "You told them they owed you nothing."


def _take_what_they_have(ctx):
    debt, who = _debt(ctx), _target(ctx)
    if debt is None or who is None:
        return "There was nothing left owed."
    _settled(ctx, debt)
    got = min(debt["food"], max(0.0, who.means.get("food")))
    who.means.add({"food": -got})
    _gain(ctx, "food", got)
    _warm_family(ctx, -0.3)
    if ctx.rng.random() < 0.3:
        ctx.state.nation.grudges[grudge_key(who.family_name, ctx.char.family_name)] = ctx.state.year
    return f"You took what {who.name} had, though it left their hearth bare."


def _work_off_debt(ctx):
    debt = _debt(ctx)
    if debt is None:
        return "There was nothing left owed."
    _settled(ctx, debt)
    _gain(ctx, "food", debt["food"] * 0.6)
    _warm_family(ctx, -0.1)
    return "They worked your ground for a year to pay what they owed."


def _wait_longer(ctx):
    debt = _debt(ctx)
    if debt is None:
        return "There was nothing left owed."
    debt["due"] = ctx.state.year + LOAN_YEARS
    _warm_family(ctx, 0.05)
    return "You told them it could wait for better years."


def _mark_as_it_is(ctx):
    _warm_family(ctx, -0.1)
    for c in members(ctx.state, ctx.event.data.get("other", "")):
        c.adjust_affinity(ctx.char.id, 0.1)
    return "You set down what everyone knows: it is not theirs."


def _mark_for_them(ctx):
    _gain(ctx, "food", GIFT_FOR_MARKS)
    _warm_family(ctx, 0.2)
    other = ctx.event.data.get("other", "")
    return "You set down what they asked, and they did not come empty-handed." + _found_out(
        ctx, 0.4, "the false marks", family=other, kept=0.75
    )


def _mark_both_claims(ctx):
    return "You set down both claims, and let others decide between them."


def _call_levy(ctx):
    ctx.state.nation.walls_mended = ctx.state.year
    _people(ctx, cohesion=-1)
    _gain(ctx, "regard", 2)
    return "Every family sent hands, grumbling, and the wall stands again."


def _levy_spare_kin(ctx):
    ctx.state.nation.walls_mended = ctx.state.year
    _people(ctx, cohesion=-1.5)
    _gain(ctx, "food", WALL_FOOD)
    others = [
        c
        for c in ctx.state.living()
        if c.settlement_id == ctx.char.settlement_id and c.family_name != ctx.char.family_name
    ]
    if not others:
        return "Every family sent hands but yours, and the wall stands again."
    family = ctx.rng.choice(others).family_name
    for c in members(ctx.state, family):
        c.adjust_affinity(ctx.char.id, -0.2)
    if ctx.rng.random() < 0.4:
        ctx.state.nation.grudges[grudge_key(family, ctx.char.family_name)] = ctx.state.year
    return (
        f"Every family sent hands but yours, and the wall stands again. "
        f"The {family} family noticed."
    )


def _ask_willing(ctx):
    ctx.state.nation.walls_mended = ctx.state.year - WALL_YEARS // 2
    _people(ctx, cohesion=0.5)
    return "Those who were willing came, and the worst of the wall was mended."


def _work_wall(ctx):
    _gain(ctx, "regard", 1)
    return "You carried earth and timber with the rest."


def _send_food_for_wall(ctx):
    return "You sent food for those at the wall instead of your own hands."


def _shirk_wall(ctx):
    if ctx.rng.random() >= FOUND_OUT:
        return "You found reasons to be elsewhere, and no one said anything."
    ctx.char.means.set("regard", ctx.char.means.get("regard") * 0.8)
    _local(ctx, cohesion=-0.5)
    return "You found reasons to be elsewhere, and people noticed who was missing."


def _surplus(ctx):
    return SURPLUS * people_scale(ctx.state)


def _shares_to_stores(ctx):
    ctx.state.nation.stores.add({"food": _surplus(ctx)})
    return "You put what came in beyond your needs into the common stores."


def _keep_shares(ctx):
    _gain(ctx, "food", SURPLUS)
    if ctx.rng.random() >= 0.3:
        return "What came in beyond your needs went to your own family, and no one asked."
    ctx.char.means.set("regard", ctx.char.means.get("regard") * 0.8)
    _people(ctx, cohesion=-2)
    return "What came in beyond your needs went to your own family, and it became known."


def _shares_to_needy(ctx):
    camps = sorted(ctx.state.settlements.values(), key=lambda s: s.plenty)
    _local(ctx, cohesion=1, plenty=3, camp=camps[0])
    _gain(ctx, "regard", 1)
    return f"You sent what came in beyond your needs to the hungriest hearths of {camps[0].name}."


def _leader_family(ctx):
    leader = ctx.state.leader
    return leader.family_name if leader else ""


def _pay_share(ctx):
    leader = ctx.state.leader
    if leader:
        leader.means.add({"food": SHARE})
        leader.adjust_affinity(ctx.char.id, 0.05)
    return "You brought your family's share to the leader's store."


def _hide_share(ctx):
    return "You brought less than your share, and said it was a lean year." + _found_out(
        ctx, 0.3, "the hidden share", family=_leader_family(ctx)
    )


def _steal_stores(ctx):
    _gain(ctx, "food", STOLEN)
    return "You filled a basket from their stores and carried it home in the dark." + _found_out(
        ctx, 0.4, "the theft"
    )


def _leave_stores(ctx):
    return "You walked past their stores and left them be."


def _guard_stores(ctx):
    _warm_family(ctx, 0.1)
    _gain(ctx, "regard", 1)
    return "You kept an eye on their stores until they came back, and told them so."


def _fighting_strength(ctx, char):
    trained = 0.3 if char.station in ("hunter", "warrior") else 0.0
    return char.health / 100 + tendencies.affinity(char.tendencies, ("harsh",)) + trained


def _strike(ctx):
    who = _target(ctx)
    if who is None:
        return "There was no one to strike."
    mine, theirs = _fighting_strength(ctx, ctx.char), _fighting_strength(ctx, who)
    heal(ctx.char, -ctx.rng.uniform(4, 14))
    heal(who, -ctx.rng.uniform(4, 14))
    who.adjust_affinity(ctx.char.id, -0.4)
    _warm_family(ctx, -0.15)
    _local(ctx, cohesion=-1)
    if ctx.rng.random() < FIGHT_STARTS_FEUD and who.family_name != ctx.char.family_name:
        ctx.state.nation.grudges[grudge_key(who.family_name, ctx.char.family_name)] = ctx.state.year
    if ctx.rng.random() < mine / max(0.1, mine + theirs):
        _gain(ctx, "regard", 2)
        return f"You struck {who.name} down before everyone. No one laughs at you now."
    _gain(ctx, "regard", -2)
    return f"You went for {who.name}, and came off the worse. People talked of it for days."


def _answer_back(ctx):
    who = _target(ctx)
    _gain(ctx, "regard", 1)
    if who:
        who.adjust_affinity(ctx.char.id, -0.2)
    return "You answered them so that the whole fire laughed, at them this time."


def _let_pass(ctx):
    return "You let it pass. Words are only words."


def _affair(ctx):
    who = _target(ctx)
    if who is None:
        return "It came to nothing."
    who.adjust_affinity(ctx.char.id, 0.4)
    ctx.char.adjust_affinity(who.id, 0.3)
    line = "You met in secret, more than once."
    if ctx.rng.random() >= AFFAIR_FOUND_OUT:
        return line
    wronged = [ctx.state.character(c.spouse_id) for c in (who, ctx.char)]
    wronged = [w for w in wronged if w and w.alive]
    for w in wronged:
        w.adjust_affinity(ctx.char.id, -0.6)
        w.adjust_affinity(who.id, -0.5)
        for kin in members(ctx.state, w.family_name):
            if kin is not w and kin is not ctx.char:
                kin.adjust_affinity(ctx.char.id, -0.2)
        if w.family_name != ctx.char.family_name:
            key = grudge_key(w.family_name, ctx.char.family_name)
            ctx.state.nation.grudges[key] = ctx.state.year
    ctx.char.means.set("regard", ctx.char.means.get("regard") * 0.85)
    return line + " It came out, as such things do."


def _keep_away(ctx):
    return "You kept away from them, though it was not easy."


def _kill(ctx):
    who = _target(ctx)
    if who is None or not who.alive:
        return "They were not there."
    family = who.family_name
    die(ctx.state, who, "a killing no one saw")
    line = f"{who.full_name} did not come back from the river."
    out = _found_out(ctx, KILLING_FOUND_OUT, "who killed them", family=family, cool=0.8, kept=0.5)
    if out:
        _local(ctx, cohesion=-3)
        ctx.state.nation.blood_owed[family] = [ctx.char.id, who.name]
        return line + f" The {family} family know who did it, and say blood is owed."
    return line + " No one knows who did it."


def _confront(ctx):
    who = _target(ctx)
    if who:
        who.adjust_affinity(ctx.char.id, 0.2)
        ctx.char.adjust_affinity(who.id, 0.1)
    return "You went to them alone and said what lay between you. It was a start."


def _let_be(ctx):
    return "You let them go their way."


def _owed_family(ctx):
    return ctx.event.data.get("family", "") if ctx.event else ""


def _pay_blood_price(ctx):
    family = _owed_family(ctx)
    ctx.state.nation.blood_owed.pop(family, None)
    for c in members(ctx.state, family):
        c.adjust_affinity(ctx.char.id, 0.3)
    return f"You paid the {family} family what a life is worth among the people. It is settled."


def _flee(ctx):
    camps = [s for s in ctx.state.settlements.values() if s.id != ctx.char.settlement_id]
    if not camps:
        return "There was nowhere to go."
    camp = ctx.rng.choice(camps)
    ctx.char.settlement_id = camp.id
    for c in _family(ctx):
        if c.age(ctx.state.year) < ADULT_AGE or c.id == ctx.char.spouse_id:
            c.settlement_id = camp.id
    return f"You left in the night with your own, and made a new hearth at {camp.name}."


def _stand_ground(ctx):
    _gain(ctx, "regard", 1)
    return "You let it be known you would be waiting for them."


def _warm_family(ctx, amount):
    for c in members(ctx.state, _family_of_matter(ctx)):
        c.adjust_affinity(ctx.char.id, amount)


def _share_grove(ctx):
    _warm_family(ctx, 0.15)
    _gain(ctx, "food", 4 * _own_land(ctx))
    return f"You gathered beside the {_family_of_matter(ctx)} family, and there was enough."


def _gather_anyway(ctx):
    _gain(ctx, "food", 10 * _own_land(ctx))
    return "You went to the grove before dawn and filled your baskets." + _found_out(
        ctx, FOUND_OUT, "the grove"
    )


def _leave_grove(ctx):
    return "You left the grove to them and looked elsewhere."


def _watch_traps(ctx):
    who = _target(ctx)
    _gain(ctx, "regard", 1)
    if who and ctx.rng.random() < 0.6:
        who.adjust_affinity(ctx.char.id, -0.2)
        return f"You lay in the reeds and caught {who.name} at your traps. Everyone heard of it."
    return "You watched your traps for nights on end, and no one came."


def _set_more(ctx):
    _gain(ctx, "food", 4 * _own_land(ctx))
    return "You set more traps and let the thief have the few."


def _empty_theirs(ctx):
    _gain(ctx, "food", 8 * _own_land(ctx))
    return "You emptied their traps in return." + _found_out(ctx, FOUND_OUT, "their traps")


def _take_to_judgement(ctx):
    _gain(ctx, "regard", 1)
    if ctx.rng.random() < 0.6:
        _gain(ctx, "food", 4)
        return "Those who judge such things set the stones back where they had been."
    _warm_family(ctx, -0.1)
    return "Those who judge such things could not say where the stones had stood."


def _move_further(ctx):
    _gain(ctx, "food", 6 * _own_land(ctx))
    return "You moved the stones back, and a little further." + _found_out(
        ctx, FOUND_OUT, "the stones"
    )


def _let_it_be(ctx):
    _local(ctx, cohesion=0.5)
    return "You let the stones lie where they were. There is land enough."


def _return_stray(ctx):
    _warm_family(ctx, 0.2)
    return f"You drove the beast back to the {_family_of_matter(ctx)} family's herd."


def _keep_stray(ctx):
    _gain(ctx, "food", 12)
    return "The beast is yours now, if anyone asks." + _found_out(ctx, FOUND_OUT, "the beast")


def _ask_reward(ctx):
    _gain(ctx, "food", 4)
    _warm_family(ctx, -0.05)
    return "You gave the beast back, for a share of its milk."


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


def _could_bring_gifts(state, char):
    return char.means.get("regard") >= MARRIAGE_STANDING


def _knows(did):
    return lambda state, char: did in state.nation.known


def _fights(state, char):
    return state.nation.known.get("warriors") in ("war_band", "all_fight")


def _plants(state, char):
    return "cultivation" in state.nation.known and char.station in ("leader", "planter")


def _judges_with_spirits(state, char):
    return say.judges(state, char) and "spirits" in state.nation.known


def _has_say(state, char):
    return say.has_say(state, char)


def _no_say(state, char):
    return not say.has_say(state, char)


def _judges(state, char):
    return say.judges(state, char)


def _not_judging(state, char):
    return not say.judges(state, char)


def _not_leading(state, char):
    return char.station != "leader"


def _lends(state, char):
    return char.means.get("food") >= LOAN


def keeps_marks(state, char):
    return "writing" in state.nation.known and (char.station == "keeper" or say.judges(state, char))


def leads_with_shares(state, char):
    return char.station == "leader" and state.nation.known.get("tribute") == "leaders_share"


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
        (),
        ("contemplative", "caring"),
        0.04,
        _judge_feud,
        {"regard": 3},
        requires=_judges,
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
        requires=_not_judging,
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
    Action(
        "accept_match",
        "Take {match} as your mate",
        "Join your life to theirs, and your family to the {family}.",
        (),
        ("caring",),
        0.02,
        _accept_match,
        {"food": 4},
        requires=_has_food(4),
    ),
    Action(
        "refuse_match",
        "Refuse the match",
        "Not this one. Their family will not be pleased.",
        (),
        ("contemplative",),
        0.0,
        _refuse_match,
    ),
    Action(
        "share_with_kin",
        "Send food to the {family} family",
        "They are your kin now; what is yours is partly theirs.",
        (),
        ("generous", "caring"),
        0.04,
        _share_with_kin,
        {"food": 6},
        requires=_has_food(6),
    ),
    Action(
        "refuse_kin",
        "Keep your food for your own",
        "Your own hearth comes first.",
        (),
        ("harsh",),
        -0.02,
        _refuse_kin,
    ),
    Action(
        "join_families",
        "Offer a marriage between the {a} and {b} families",
        "Gifts from both, a son of one for a daughter of the other: kin do not feud.",
        (),
        ("generous", "caring"),
        0.04,
        _join_families,
        {"food": 10, "regard": 2},
        requires=_could_bring_gifts,
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
        "hear_them_out",
        "Go to {rival}'s camp and hear them out",
        "Sit at their fire, and listen to whoever would rather follow them.",
        ("leader",),
        ("caring", "contemplative"),
        0.04,
        _hear_them_out,
        {"food": 4, "regard": 1},
        requires=_has_food(4),
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
        requires=_has_say,
    ),
    Action(
        "send_on",
        "Send them on their way",
        "Point them to the next camp. Your food is for your own.",
        (),
        ("acquisitive",),
        -0.02,
        _send_on,
        requires=_has_say,
    ),
    Action(
        "speak_for_stranger",
        "Say they should be taken in",
        "It is not yours to decide, but you can be heard.",
        (),
        ("generous",),
        0.02,
        _speak_for_stranger,
        requires=_no_say,
    ),
    Action(
        "speak_against_stranger",
        "Say they should be sent on",
        "It is not yours to decide, but you can be heard.",
        (),
        ("acquisitive",),
        -0.01,
        _speak_against_stranger,
        requires=_no_say,
    ),
    Action(
        "take_in_family",
        "Let them settle",
        "More hands, more mouths.",
        (),
        ("generous",),
        0.03,
        _take_in_family,
        {"regard": 1},
        requires=_has_say,
    ),
    Action(
        "turn_away_family",
        "Turn them away",
        "There is no room, or no wish to make it.",
        (),
        ("harsh",),
        -0.02,
        _turn_away_family,
        requires=_has_say,
    ),
    # what is yours, and what is theirs
    Action(
        "share_grove",
        "Gather there beside them",
        "There is enough for two families, if both take care.",
        ("gatherer",),
        ("generous",),
        0.03,
        _share_grove,
    ),
    Action(
        "gather_anyway",
        "Go there before dawn",
        "No one owns what grows wild. Or so you will say if anyone asks.",
        ("gatherer",),
        ("acquisitive",),
        -0.03,
        _gather_anyway,
    ),
    Action(
        "leave_grove",
        "Leave it to them",
        "Look for food elsewhere.",
        ("gatherer",),
        ("contemplative",),
        0.01,
        _leave_grove,
    ),
    Action(
        "watch_traps",
        "Lie in wait by your traps",
        "Catch whoever it is, and let everyone know.",
        ("fisher",),
        ("harsh",),
        -0.01,
        _watch_traps,
        {"hands": 1},
    ),
    Action(
        "set_more",
        "Set more traps",
        "Let the thief have a few; there are fish enough.",
        ("fisher",),
        ("generous", "diligent"),
        0.02,
        _set_more,
        {"hands": 1},
    ),
    Action(
        "empty_theirs",
        "Empty their traps in return",
        "Take back what was taken, and a little more.",
        ("fisher",),
        ("acquisitive", "harsh"),
        -0.04,
        _empty_theirs,
    ),
    Action(
        "take_to_judgement",
        "Take it to those who judge",
        "Let someone else say where the stones stood.",
        ("planter",),
        ("contemplative",),
        0.02,
        _take_to_judgement,
        {"regard": 1},
    ),
    Action(
        "move_further",
        "Move the stones back, and further",
        "They started it.",
        ("planter",),
        ("acquisitive", "harsh"),
        -0.04,
        _move_further,
        {"hands": 1},
    ),
    Action(
        "let_it_be",
        "Let the stones lie",
        "A field's edge is not worth a feud.",
        ("planter",),
        ("generous", "contemplative"),
        0.03,
        _let_it_be,
    ),
    Action(
        "return_stray",
        "Drive it back to them",
        "It is theirs.",
        ("herder",),
        ("generous",),
        0.03,
        _return_stray,
    ),
    Action(
        "keep_stray",
        "Keep it among yours",
        "Who could tell one beast from another?",
        ("herder",),
        ("acquisitive",),
        -0.04,
        _keep_stray,
    ),
    Action(
        "ask_reward",
        "Give it back, for a share",
        "You fed it, after all.",
        ("herder",),
        ("acquisitive",),
        0.0,
        _ask_reward,
    ),
    # lies, trade, and the people's own ways
    Action(
        "spread_tale",
        "Spread a tale about them",
        "Not quite a lie. Not quite true.",
        (),
        ("ambitious", "harsh"),
        -0.05,
        _spread_tale,
    ),
    Action(
        "praise_them",
        "Speak well of them",
        "Their standing is no loss to yours.",
        (),
        ("generous",),
        0.03,
        _praise_them,
    ),
    Action(
        "say_nothing",
        "Say nothing",
        "Let others talk.",
        (),
        ("contemplative",),
        0.0,
        _say_nothing,
    ),
    Action(
        "short_measure",
        "Give short measure",
        "They will not count it.",
        (),
        ("acquisitive",),
        -0.04,
        _short_measure,
    ),
    Action(
        "fair_trade",
        "Trade fairly",
        "What you would want for yourself.",
        (),
        ("generous",),
        0.02,
        _fair_trade,
    ),
    Action(
        "bride_price",
        "Wed, for a bride-price",
        "Goods from the groom's kin to the bride's, as is done.",
        (),
        ("acquisitive",),
        0.0,
        _bride_price,
    ),
    Action(
        "take_captives",
        "Take captives in return",
        "Hands to work, for what they took.",
        ("leader", "warrior"),
        ("harsh", "acquisitive"),
        -0.02,
        _take_captives,
        requires=_fights,
    ),
    Action(
        "set_blood_price",
        "Set a price for the wrong",
        "Food and goods instead of blood, paid by the family in the wrong.",
        (),
        ("contemplative",),
        0.01,
        _set_blood_price,
        {"regard": 2},
        requires=_judges,
    ),
    Action(
        "ordeal",
        "Put them to the ordeal",
        "Fire or water: the unseen will show who is in the right.",
        (),
        ("contemplative",),
        0.0,
        _ordeal,
        {"regard": 1},
        requires=_judges_with_spirits,
    ),
    Action(
        "keep_seed",
        "Keep the seed back",
        "If it is eaten now, there will be nothing to plant.",
        (),
        ("diligent", "harsh"),
        0.0,
        _keep_seed,
        requires=_plants,
    ),
    # what grows with later ideas
    Action(
        "lend_food",
        "Lend it",
        "To be given back when the harvests turn.",
        (),
        ("caring",),
        0.02,
        _lend_food,
        requires=_lends,
    ),
    Action(
        "lend_for_more",
        "Lend it, for more back",
        "Food now is worth more than food later.",
        (),
        ("acquisitive",),
        -0.02,
        _lend_for_more,
        requires=_lends,
    ),
    Action(
        "give_outright",
        "Give it outright",
        "What would you do with a debt?",
        (),
        ("generous",),
        0.04,
        _give_outright,
        requires=_lends,
    ),
    Action(
        "refuse_loan",
        "Refuse",
        "You have your own to feed.",
        (),
        ("acquisitive",),
        -0.01,
        _refuse_loan,
    ),
    Action(
        "forgive_debt",
        "Forgive the debt",
        "Let it go.",
        (),
        ("generous",),
        0.04,
        _forgive_debt,
    ),
    Action(
        "take_what_they_have",
        "Take what they have",
        "A debt is a debt.",
        (),
        ("harsh", "acquisitive"),
        -0.04,
        _take_what_they_have,
    ),
    Action(
        "work_off_debt",
        "Have them work it off",
        "Their hands on your ground, for a year.",
        (),
        ("ambitious",),
        -0.01,
        _work_off_debt,
    ),
    Action(
        "wait_longer",
        "Let it wait",
        "Better years will come.",
        (),
        ("caring",),
        0.02,
        _wait_longer,
    ),
    Action(
        "mark_as_it_is",
        "Mark it as it is",
        "The marks should say what is so.",
        (),
        ("studious",),
        0.03,
        _mark_as_it_is,
        requires=keeps_marks,
    ),
    Action(
        "mark_for_them",
        "Mark it as they ask",
        "Once it is in the marks, it is so.",
        (),
        ("acquisitive",),
        -0.05,
        _mark_for_them,
        requires=keeps_marks,
    ),
    Action(
        "mark_both_claims",
        "Mark both claims",
        "It is not yours to settle.",
        (),
        ("contemplative",),
        0.01,
        _mark_both_claims,
        requires=keeps_marks,
    ),
    Action(
        "call_levy",
        "Call every family to the wall",
        "Hands from every hearth, for as long as it takes.",
        (),
        ("diligent",),
        0.02,
        _call_levy,
        requires=_has_say,
    ),
    Action(
        "levy_spare_kin",
        "Call the others to the wall",
        "Your own family has work enough already.",
        (),
        ("ambitious", "acquisitive"),
        -0.04,
        _levy_spare_kin,
        requires=_has_say,
    ),
    Action(
        "ask_willing",
        "Ask for those willing",
        "No one made to come.",
        (),
        ("caring",),
        0.01,
        _ask_willing,
        requires=_has_say,
    ),
    Action(
        "work_wall",
        "Go to the wall",
        "Earth and timber, with everyone else.",
        (),
        ("diligent",),
        0.02,
        _work_wall,
        {"hands": 2},
        requires=_no_say,
    ),
    Action(
        "send_food_for_wall",
        "Send food instead",
        "Others' hands, fed from your hearth.",
        (),
        ("generous",),
        0.01,
        _send_food_for_wall,
        {"food": WALL_FOOD},
        requires=_no_say,
    ),
    Action(
        "shirk_wall",
        "Keep away from it",
        "There is always something else to do.",
        (),
        ("indulgent",),
        -0.02,
        _shirk_wall,
        requires=_no_say,
    ),
    Action(
        "shares_to_stores",
        "Put it in the common stores",
        "It was given for the people.",
        (),
        ("diligent",),
        0.02,
        _shares_to_stores,
        requires=leads_with_shares,
    ),
    Action(
        "keep_shares",
        "Keep it for your family",
        "It was given to you.",
        (),
        ("acquisitive",),
        -0.04,
        _keep_shares,
        requires=leads_with_shares,
    ),
    Action(
        "shares_to_needy",
        "Send it to the hungriest",
        "Those with least gave the most.",
        (),
        ("generous", "caring"),
        0.04,
        _shares_to_needy,
        requires=leads_with_shares,
    ),
    Action(
        "pay_share",
        "Bring your share",
        "As every family does.",
        (),
        ("diligent",),
        0.01,
        _pay_share,
        {"food": SHARE},
    ),
    Action(
        "hide_share",
        "Bring less, and say it was a lean year",
        "Who counts?",
        (),
        ("acquisitive",),
        -0.03,
        _hide_share,
    ),
    # temptations
    Action(
        "steal_stores",
        "Take from their stores",
        "No one is watching. They have more than they need.",
        (),
        ("acquisitive",),
        -0.06,
        _steal_stores,
    ),
    Action(
        "leave_stores",
        "Leave them be",
        "It is not yours.",
        (),
        ("contemplative",),
        0.01,
        _leave_stores,
    ),
    Action(
        "guard_stores",
        "Watch over them till they return",
        "Others may not be so honest.",
        (),
        ("caring",),
        0.02,
        _guard_stores,
        {"hands": 1},
    ),
    Action(
        "strike",
        "Strike them",
        "Answer with your fists, here and now.",
        (),
        ("harsh",),
        -0.05,
        _strike,
    ),
    Action(
        "answer_back",
        "Answer them in kind",
        "A sharper tongue, before the same fire.",
        (),
        ("ambitious",),
        -0.01,
        _answer_back,
    ),
    Action(
        "let_pass",
        "Let it pass",
        "Say nothing. It will be forgotten.",
        (),
        ("contemplative",),
        0.03,
        _let_pass,
    ),
    Action(
        "affair",
        "Meet them in secret",
        "What no one knows harms no one. Or so it seems.",
        (),
        ("indulgent",),
        -0.05,
        _affair,
    ),
    Action(
        "keep_away",
        "Keep away from them",
        "Some fires are better left unlit.",
        (),
        ("contemplative",),
        0.01,
        _keep_away,
    ),
    Action(
        "kill",
        "Follow them to the river",
        "No one else will be there.",
        (),
        ("harsh",),
        -0.3,
        _kill,
    ),
    Action(
        "confront",
        "Go and speak with them",
        "Say what lies between you, alone.",
        (),
        ("caring",),
        0.03,
        _confront,
    ),
    Action(
        "let_be",
        "Let them go",
        "Whatever lies between you can wait.",
        (),
        ("contemplative",),
        0.02,
        _let_be,
    ),
    Action(
        "pay_blood_price",
        "Pay the blood-price",
        "Food and goods for a life, as the people reckon it.",
        (),
        ("generous",),
        0.04,
        _pay_blood_price,
        {"food": 30},
        requires=_has_food(30),
    ),
    Action(
        "flee",
        "Take your own and go",
        "Make a new hearth at another camp, out of their reach.",
        (),
        ("contemplative",),
        0.0,
        _flee,
    ),
    Action(
        "stand_ground",
        "Wait for them",
        "If they come, they come.",
        (),
        ("harsh",),
        -0.01,
        _stand_ground,
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
