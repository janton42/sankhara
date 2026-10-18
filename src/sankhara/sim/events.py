"""Yearly events and the matters at hand.

Some events are only news (a kind year, a sickness, a fall). Others are matters
the player could meet: they carry the ways the player's role can answer them
(`answers`, action ids from `actions.py`). Some grow out of the people's state
and last as long as it does (hunger, quarrels, low stores, plenty, talk of who
should lead); some come by chance (a stranger, a feud, a raid); some come with a
role (a hunter's share of a great kill, a keeper asked for the oldest songs).

A matter is `expected` of the player when their role gives them a plain duty in
it; ignoring it then costs karma, and any answer meets it, each with its own
weight. Meeting it guarantees nothing. Outcomes are deliberately not fair.
"""

from dataclasses import dataclass

from sankhara.sim import discoveries
from sankhara.sim.actions import ACTIONS, could_lead, open_to
from sankhara.sim.nation import adjust_settlements, people_scale, refresh_averages
from sankhara.sim.people import (
    LEADER_AGE,
    die,
    family_of,
    grudge,
    grudge_key,
    leader_failing,
    members,
    standing,
    support,
)
from sankhara.sim.peoples import raid_chance
from sankhara.sim.state import EventInstance
from sankhara.sim.stations import ADULT_AGE
from sankhara.sim.world import camp_tiles, is_watery

HUNGER_THRESHOLD = 0.05  # a shortfall bigger than this share of need is felt as hunger
LOW_STORES = 15  # common food per unit of people_scale below which the stores are low
FULL_STORES = 70  # ...and above which there is plenty
TALK_OF_LEADING = 0.35  # standing, relative to the leader's, at which people say you should lead


@dataclass(frozen=True)
class EventDef:
    kind: str
    chance: object  # (state, char) -> probability this year
    build: object  # (state, char, rng) -> EventInstance | None, applying immediate effects
    resolve: object = None  # (state, event, taken, rng) -> str | None
    answers: tuple = ()  # every way of meeting it; each is offered if open to the character
    expects: tuple = ()  # answers that, if open to the character, make it expected of them
    penalty: float = 0.0


def _is_leader(char):
    return char.station == "leader"


# --- the whole people -------------------------------------------------------


def _lean_year(state, char, rng):
    state.modifiers["harvest"] = state.modifiers.get("harvest", 1.0) * 0.7
    return EventInstance("lean_year", "The rains failed. Game is thin and the plants are poor.")


def _rich_year(state, char, rng):
    state.modifiers["harvest"] = state.modifiers.get("harvest", 1.0) * 1.25
    return EventInstance("rich_year", "A kind year: the land is full of food.")


def _sickness(state, char, rng):
    state.modifiers["plague"] = rng.uniform(0.04, 0.12)
    for c in state.living():
        c.health -= rng.uniform(0, 22)
    return EventInstance("sickness", "A sickness moved from camp to camp, sparing no one.")


def _flood(state, char, rng):
    wet = [s for s in state.settlements.values() if any(is_watery(t) for t in camp_tiles(state, s))]
    if not wet:
        return None
    s = rng.choice(wet)
    s.population *= 0.96
    state.modifiers[f"harvest:{s.id}"] = 0.75
    return EventInstance(
        "flood",
        f"The water rose around {s.name} and swept shelters away.",
        s.id,
        data={"camp": s.name},
    )


def _omen(state, char, rng):
    adjust_settlements(state, cohesion=rng.choice([-2, 2]))
    return EventInstance(
        "omen", "A light with a tail hung in the sky for a month. Nobody agreed what it meant."
    )


def _spark(state, char, rng):
    options = discoveries.available(state)
    if not options:
        return None
    d = rng.choice(options)
    discoveries.add_insight(state, d.id, d.cost * 0.25)
    return EventInstance("spark", d.hint)


def _short(s):
    return s.food_balance < -HUNGER_THRESHOLD * s.population * 0.1


def _hungry(state):
    return any(_short(x) for x in state.settlements.values())


def _hunger(state, char, rng):
    hungry = [s.name for s in state.settlements.values() if _short(s)]
    return EventInstance("hunger", f"People are going hungry in {', '.join(hungry)}.")


def _stores_low(state):
    return state.nation.stores.get("food") < LOW_STORES * people_scale(state)


def _low_stores(state, char, rng):
    return EventInstance("low_stores", "The common stores are running low.")


def _plenty(state):
    if _hungry(state):
        return False
    full = state.nation.stores.get("food") > FULL_STORES * people_scale(state)
    return full or state.modifiers.get("harvest", 1.0) > 1.0


def _plenty_build(state, char, rng):
    return EventInstance("plenty", "There is food to spare this year.")


def _discord(state, char, rng):
    return EventInstance("discord", "The camps are full of quarrels and old grudges.")


def _discord_resolve(state, event, taken, rng):
    if not taken and event.expected:
        adjust_settlements(state, cohesion=-4)
        return "The quarrels festered."
    return None


def _feud(state, char, rng):
    """Two families fall out: known ones from the player's camp when there are enough of
    them, so the grudge is carried by people the player knows."""
    from sankhara.entities.namer import make_family_name

    names = sorted(
        {
            c.family_name
            for c in state.living()
            if c.settlement_id == char.settlement_id
            and c.family_name != char.family_name
            and c.age(state.year) >= ADULT_AGE
        }
    )
    old = [
        key.split("|")
        for key in state.nation.grudges
        if set(key.split("|")) <= set(names) and grudge(state, *key.split("|"))
    ]
    text = "The {a} and {b} families are at each other's throats over a broken promise."
    if old and rng.random() < OLD_GRUDGE_FLARES:
        a, b = rng.choice(old)
        text = "The old grudge between the {a} and {b} families has flared up again."
    elif len(names) >= 2:
        a, b = rng.sample(names, 2)
    else:
        a = make_family_name(state.nation.culture, rng)
        b = make_family_name(state.nation.culture, rng)
    return EventInstance("feud", text.format(a=a, b=b), data={"a": a, "b": b})


def _estrange(state, a, b, amount):
    """Members of two families think worse of each other."""
    for x in members(state, a):
        for y in members(state, b):
            x.adjust_affinity(y.id, -amount)
            y.adjust_affinity(x.id, -amount)


def _feud_resolve(state, event, taken, rng):
    a, b = event.data["a"], event.data["b"]
    peacemaking = {"judge_feud", "make_peace"} & set(event.data.get("taken_with", []))
    if peacemaking and rng.random() < 0.8:
        state.nation.grudges.pop(grudge_key(a, b), None)
        return f"The {a} and {b} families made their peace."
    if not taken and not event.expected and rng.random() < 0.5:
        return None  # the player stood aside, and it blew over
    _estrange(state, a, b, 0.3)
    state.nation.grudges[grudge_key(a, b)] = state.year  # remembered by their children
    if rng.random() < 0.4:
        men = [c for c in members(state, a) if c.gender == "male" and not c.is_player]
        if men:
            victim = rng.choice(men)
            die(state, victim, "a feud")
            who = victim.full_name
        else:
            state.seat.population = max(12.0, state.seat.population - 1)
            who = f"A man of the {a} family"
        adjust_settlements(state, cohesion=-3)
        return f"{who} was killed. Nobody will say who did it."
    adjust_settlements(state, cohesion=-1)
    return f"The {a} and {b} families no longer speak."


# --- who would lead ----------------------------------------------------------------

OLD_GRUDGE_FLARES = 0.7  # a feud that flares between families with an old grudge
RIVAL_SHARE = 0.6  # standing, relative to the leader's, at which someone is a rival to them
DIVIDED_COHESION = 0.5  # a year's fraying while the people are divided
FOLLOWERS_DRAWN = 0.05  # how much a rival's unanswered talk warms their camp toward them
RIVAL_REGARD = 15


def rival(state):
    """Someone the people might look to instead of the leader: the most respected grown
    person who is not the leader, if they come near enough to the leader's standing."""
    leader = state.leader
    if leader is None:
        return None
    others = [
        c
        for c in state.living()
        if c.id != leader.id
        and c.age(state.year) >= LEADER_AGE
        and c.means.get("regard") >= RIVAL_REGARD
        and state.nation.succession != "lineage"
    ]
    if not others:
        return None
    best = max(others, key=standing)
    return best if standing(best) >= RIVAL_SHARE * standing(leader) else None


def divided_year(state):
    """When more of the people's weight stands behind a rival than behind the leader, the
    camps divide: the rival's camp frays each year until one side gives way. Returns a
    line when the people divide or come back together."""
    nation = state.nation
    leader = state.leader
    r = rival(state)
    split = (
        r is not None
        and leader is not None
        and support(state, r, leader) > max(0.0, support(state, leader, r))
    )
    if split:
        adjust_settlements(state, cohesion=-DIVIDED_COHESION)
        adjust_settlements(state, cohesion=-DIVIDED_COHESION, only=r.settlement_id)
    if split == bool(nation.divided):
        return ""
    nation.divided = r.id if split else 0
    if split:
        return f"The people are divided between {leader.full_name} and {r.full_name}."
    return "The people are of one mind again about who leads them."


def _npc_rival(state, char):
    r = rival(state)
    return r if r is not None and not r.is_player else None


def _rival_build(state, char, rng):
    r = _npc_rival(state, char)
    if r is None:
        return None
    return EventInstance(
        "rival",
        f"{r.full_name} has begun to say openly that they, not you, should lead the people.",
        target_id=r.id,
        data={"rival": r.name},
    )


def _rival_resolve(state, event, taken, rng):
    r = state.character(event.target_id)
    if taken or r is None or not r.alive:
        return None
    r.means.add({"regard": 2})
    adjust_settlements(state, cohesion=-1)
    # and draws people after them
    for c in state.living():
        if c.settlement_id == r.settlement_id and c is not r and c.age(state.year) >= ADULT_AGE:
            c.adjust_affinity(r.id, FOLLOWERS_DRAWN)
    return f"Talk of {r.name} leading went unanswered, and grew."


def _take_sides_build(state, char, rng):
    r = _npc_rival(state, char)
    leader = state.leader
    if r is None or leader is None or r.id == char.id:
        return None
    return EventInstance(
        "take_sides",
        f"{r.full_name} asks you to speak for them against {leader.name}, who leads the people.",
        target_id=r.id,
        data={"rival": r.name, "leader": leader.name},
    )


def _knows_fighting(state):
    return "warriors" in state.nation.known


def outshines(state, char):
    """Whether the people look to this character more than to the one who leads them, by
    enough that they talk of it."""
    leader = state.leader
    if leader is None or not could_lead(state, char):
        return False
    return standing(char) > TALK_OF_LEADING * standing(leader)


def talk_of_leading(state, char):
    """Whether people have begun to say this character should lead."""
    if not could_lead(state, char):
        return False
    return leader_failing(state) or outshines(state, char)


def _could_lead_build(state, char, rng):
    leader = state.leader
    name = leader.name if leader else "the one who leads"
    return EventInstance(
        "could_lead",
        "Some have begun to say you should lead the people.",
        data={"leader": name},
    )


def _raid(state, char, rng):
    hostile = [n for n in state.neighbours.values() if raid_chance(state, n) > 0]
    if not hostile:
        return None
    n = max(hostile, key=lambda x: raid_chance(state, x))
    stores = state.nation.stores
    stores.set("food", stores.get("food") * 0.7)
    camp = rng.choice(list(state.settlements.values()))
    camp.population = max(12.0, camp.population - rng.randint(1, 4))
    camp.cohesion = max(0.0, camp.cohesion - 2)
    refresh_averages(state)
    return EventInstance(
        "raid",
        f"The {n.name} raided {camp.name} by night, took food and left people dead.",
        camp.id,
        data={"neighbour": n.id, "camp": camp.name},
    )


def _raid_resolve(state, event, taken, rng):
    n = state.neighbour(event.data.get("neighbour"))
    if n is None:
        return None
    if "stand_guard" in event.data.get("taken_with", []):
        stores = state.nation.stores
        stores.add({"food": stores.get("food") * 0.1})
        return (
            f"The {n.name} came back for more and found your band waiting. They left with nothing."
        )
    if "answer_raid" in event.data.get("taken_with", []):
        if rng.random() < 0.55 + 0.4 * n.relations:
            n.relations = min(1.0, n.relations + 0.2)
            return f"The {n.name} sent back some of what they took, and gifts besides."
        return f"The {n.name} laughed at our messengers."
    if not taken and event.expected:
        adjust_settlements(state, cohesion=-3)
        return "Nothing was done about the raid. People talk of little else."
    return None


def _challenge(state, char, rng):
    met = [n for n in state.neighbours.values() if n.met]
    if not met:
        return None
    n = rng.choice(met)
    return EventInstance(
        "challenge",
        f"A champion of the {n.name} has come to the border and called for one of ours to "
        f"fight him, for honour and not for blood.",
        data={"neighbour": n.id},
    )


def _beast(state, char, rng):
    return EventInstance("beast", "A great cat has been taking people at the edge of the camps.")


def _beast_resolve(state, event, taken, rng):
    if not taken and not event.expected:
        return None  # others went after it; the player wasn't among them
    hunted = "hunt_beast" in event.data.get("taken_with", [])
    if hunted and rng.random() < 0.7:
        state.player.means.add({"regard": 3})
        return "The cat was hunted down and its skin hung by the fire."
    if hunted and rng.random() < 0.3:
        state.player.health -= 20
        return "The cat was killed, but it mauled you first."
    lost = rng.randint(1, 3) - ("guard_young" in event.data.get("taken_with", []))
    state.seat.population = max(12.0, state.seat.population - max(0, lost))
    return "The cat took more people before it moved on." if lost > 0 else None


# --- near you --------------------------------------------------------------


def _neighbours_of(state, char):
    family = {c.id for _, c in family_of(state, char)}
    return [
        c
        for c in state.living()
        if c.settlement_id == char.settlement_id and not c.is_player and c.id not in family
    ]


def _stranger(state, char, rng):
    return EventInstance(
        "stranger", "A stranger came to your fire at dusk, alone and half-starved."
    )


def _stranger_resolve(state, event, taken, rng):
    welcomed = "welcome_stranger" in event.data.get("taken_with", [])
    if welcomed and rng.random() < 0.12:
        state.player.means.set("food", state.player.means.get("food") * 0.7)
        return "In the morning the stranger was gone, and so was some of your food."
    return None


def _lost_child(state, char, rng):
    near = [c for c in _neighbours_of(state, char) if c.children]
    who = rng.choice(near) if near else None
    whose = f"{who.name}'s child" if who else "A child"
    return EventInstance(
        "lost_child",
        f"{whose} has wandered off and not come back.",
        target_id=who.id if who else None,
    )


def _lost_child_resolve(state, event, taken, rng):
    parent = state.character(event.target_id)
    found = rng.random() < (0.75 if taken else 0.45)
    if parent and taken:
        parent.adjust_affinity(state.player_id, 0.3 if found else 0.15)
    if found:
        return "The child was found, cold and frightened but alive."
    return "The child was never found."


def _dying_elder(state, char, rng):
    old = [c for c in _neighbours_of(state, char) if c.age(state.year) >= 55]
    old += [c for _, c in family_of(state, char) if c.age(state.year) >= 55]
    if not old:
        return None
    who = rng.choice(old)
    who.health = min(who.health, 8)
    return EventInstance(
        "dying_elder", f"Old {who.full_name} is dying and asks for you.", target_id=who.id
    )


def _family(state, char):
    return [c for _, c in family_of(state, char)]


def _relative_ill(state, char, rng):
    fam = _family(state, char)
    if not fam:
        return None
    target = rng.choice(fam)
    target.health -= 20
    rel = next(r for r, c in family_of(state, char) if c.id == target.id).lower()
    return EventInstance(
        "relative_ill",
        f"Your {rel} {target.name} has fallen badly ill.",
        target_id=target.id,
    )


def _sick_neighbour(state, char, rng):
    near = _neighbours_of(state, char)
    if not near:
        return None
    n = rng.choice(near)
    n.health -= 20
    return EventInstance(
        "sick_neighbour",
        f"{n.full_name} has fallen ill and has no one to look after them.",
        target_id=n.id,
    )


def _ill_resolve(state, event, taken, rng):
    target = state.character(event.target_id)
    if not target or not target.alive:
        return None
    if rng.random() < (0.2 if taken else 0.45):
        die(state, target, "sickness")
        return f"{target.full_name} died." + (" You did all you could." if taken else "")
    if not taken:
        target.adjust_affinity(state.player_id, -0.3)
        return f"{target.full_name} recovered, no thanks to you."
    return f"{target.full_name} recovered."


def _idler(state, char, rng):
    near = [c for c in _neighbours_of(state, char) if c.age(state.year) >= 16]
    if not near:
        return None
    who = rng.choice(near)
    return EventInstance(
        "idler", f"{who.full_name} does little, and eats what others bring in.", target_id=who.id
    )


# --- what each role meets -------------------------------------------------------


def _great_kill(state, char, rng):
    return EventInstance("great_kill", "The hunters have brought down a great beast together.")


def _deep_songs(state, char, rng):
    return EventInstance(
        "deep_songs", "The young keep asking about the oldest songs, the ones few still know."
    )


def _asks_for_tools(state, char, rng):
    near = _neighbours_of(state, char)
    if not near:
        return None
    who = rng.choice(near)
    return EventInstance(
        "asks_for_tools", f"{who.full_name} has asked you for a good blade.", target_id=who.id
    )


def _needs_goods(state, char, rng):
    near = _neighbours_of(state, char)
    if not near:
        return None
    who = rng.choice(near)
    return EventInstance(
        "needs_goods",
        f"{who.full_name}'s family badly needs what you carry.",
        target_id=who.id,
    )


# --- you ----------------------------------------------------------------------


def _illness(state, char, rng):
    char.health -= 15
    return EventInstance("illness", "You fell ill and lay shivering for much of the winter.")


def _injury(state, char, rng):
    char.health -= 10
    return EventInstance("injury", "A bad fall left you limping for months.")


def _windfall(state, char, rng):
    char.means.add({"food": 10})
    return EventInstance("windfall", "You came upon a hollow tree full of honey.")


def _theft(state, char, rng):
    char.means.set("food", char.means.get("food") * 0.6)
    return EventInstance("theft", "Someone has been stealing from your family's food.")


def _role(*stations, chance):
    return lambda s, c: chance if c.station in stations else 0.0


EVENTS = [
    # what lasts as long as the people's state does
    EventDef(
        "hunger",
        lambda s, c: 0.9 if _hungry(s) else 0.0,
        _hunger,
        answers=("open_stores", "share_food", "bring_food", "keep_close"),
        expects=("open_stores", "share_food"),
        penalty=0.1,
    ),
    EventDef(
        "discord",
        lambda s, c: 0.8 if s.nation.cohesion < 35 else 0.0,
        _discord,
        _discord_resolve,
        answers=("settle_quarrels", "call_together", "drive_out", "speak_at_fires"),
        expects=("settle_quarrels", "call_together"),
        penalty=0.07,
    ),
    EventDef(
        "low_stores",
        lambda s, c: 0.7 if _stores_low(s) and not _hungry(s) else 0.0,
        _low_stores,
        answers=("great_hunt", "stock_stores"),
    ),
    EventDef(
        "could_lead",
        lambda s, c: 0.4 if talk_of_leading(s, c) else 0.0,
        _could_lead_build,
        answers=("stand_forward", "back_leader"),
    ),
    EventDef(
        "rival",
        lambda s, c: 0.3 if _is_leader(c) and _npc_rival(s, c) else 0.0,
        _rival_build,
        _rival_resolve,
        answers=("win_over", "make_room", "face_down"),
    ),
    EventDef(
        "take_sides",
        lambda s, c: 0.12 if not _is_leader(c) and _npc_rival(s, c) else 0.0,
        _take_sides_build,
        answers=("back_rival", "back_leader", "stay_out"),
    ),
    # chance
    EventDef("lean_year", lambda s, c: 0.09, _lean_year),
    EventDef("rich_year", lambda s, c: 0.09, _rich_year),
    EventDef(
        "plenty",
        lambda s, c: 0.6 if _plenty(s) else 0.0,
        _plenty_build,
        answers=("feast_all", "larger_share", "take_more", "feast"),
    ),
    EventDef("sickness", lambda s, c: 0.035, _sickness, answers=("nurse_sick",)),
    EventDef("flood", lambda s, c: 0.04, _flood, answers=("help_camp",)),
    EventDef("omen", lambda s, c: 0.03, _omen, answers=("good_signs", "true_signs")),
    EventDef("spark", lambda s, c: 0.08, _spark),
    EventDef(
        "feud",
        lambda s, c: 0.04 + (0.08 if s.nation.cohesion < 45 else 0.0),
        _feud,
        _feud_resolve,
        answers=("judge_feud", "make_peace", "side_with"),
        expects=("judge_feud",),
        penalty=0.06,
    ),
    EventDef(
        "raid",
        lambda s, c: max((raid_chance(s, n) for n in s.neighbours.values()), default=0.0),
        _raid,
        _raid_resolve,
        answers=("answer_raid", "stand_guard", "avenge_raid", "help_camp"),
        expects=("answer_raid", "stand_guard"),
        penalty=0.06,
    ),
    EventDef(
        "challenge",
        lambda s, c: 0.12 if c.station == "warrior" and _knows_fighting(s) else 0.0,
        _challenge,
        answers=("meet_challenge", "decline_challenge"),
    ),
    EventDef(
        "beast",
        lambda s, c: 0.04,
        _beast,
        _beast_resolve,
        answers=("hunt_beast", "guard_young"),
        expects=("hunt_beast",),
        penalty=0.05,
    ),
    # near you
    EventDef(
        "stranger",
        lambda s, c: 0.07,
        _stranger,
        _stranger_resolve,
        answers=("welcome_stranger", "send_on"),
        expects=("welcome_stranger",),
        penalty=0.05,
    ),
    EventDef(
        "lost_child",
        lambda s, c: 0.04,
        _lost_child,
        _lost_child_resolve,
        answers=("search",),
        expects=("search",),
        penalty=0.05,
    ),
    EventDef(
        "dying_elder",
        lambda s, c: 0.06,
        _dying_elder,
        answers=("sit_with_dying", "ask_memory"),
        expects=("sit_with_dying",),
        penalty=0.04,
    ),
    EventDef(
        "relative_ill",
        lambda s, c: 0.12 * c.family_stability,
        _relative_ill,
        _ill_resolve,
        answers=("tend_relative",),
        expects=("tend_relative",),
        penalty=0.08,
    ),
    EventDef(
        "sick_neighbour",
        lambda s, c: 0.07,
        _sick_neighbour,
        _ill_resolve,
        answers=("tend_relative",),
        expects=("tend_relative",),
        penalty=0.04,
    ),
    EventDef("idler", lambda s, c: 0.05, _idler, answers=("find_work", "shame_idler")),
    # what each role meets
    EventDef(
        "great_kill",
        _role("hunter", chance=0.25),
        _great_kill,
        answers=("share_evenly", "feed_weak", "best_cut"),
    ),
    EventDef(
        "deep_songs",
        _role("keeper", chance=0.2),
        _deep_songs,
        answers=("teach_deep", "hold_secrets"),
    ),
    EventDef(
        "asks_for_tools",
        _role("maker", chance=0.3),
        _asks_for_tools,
        answers=("make_for", "ask_return", "fine_work"),
    ),
    EventDef(
        "needs_goods",
        _role("trader", chance=0.3),
        _needs_goods,
        answers=("fair_measure", "hard_bargain"),
    ),
    # you
    EventDef("illness", lambda s, c: 0.06, _illness),
    EventDef("injury", lambda s, c: 0.04, _injury),
    EventDef("windfall", lambda s, c: 0.04, _windfall),
    EventDef("theft", lambda s, c: 0.03, _theft),
]
EVENT_DEFS = {e.kind: e for e in EVENTS}
WHOLE_PEOPLE = {
    "hunger",
    "discord",
    "low_stores",
    "lean_year",
    "rich_year",
    "plenty",
    "sickness",
    "flood",
    "omen",
    "spark",
    "feud",
    "raid",
    "beast",
}
LASTING = ("hunger", "discord", "low_stores", "plenty")  # matters that follow the people's state
MAX_EVENTS = 5


def offer(state, char, event):
    """Fill in which answers this character has, and whether the matter is expected of them."""
    d = EVENT_DEFS[event.kind]
    event.answers = [a for a in d.answers if open_to(state, char, ACTIONS[a])]
    event.expected = any(a in d.expects for a in event.answers)
    event.penalty = d.penalty if event.expected else 0.0
    if event.kind == "could_lead" and "back_leader" in event.answers:
        event.data.setdefault("leader", state.leader.name)
    return event


def generate_events(state, char, whole_people_only=False):
    """Roll this year's events, applying their immediate effects."""
    rng = state.rng()
    out = []
    for e in EVENTS:
        if whole_people_only and e.kind not in WHOLE_PEOPLE:
            continue
        if len(out) >= MAX_EVENTS:
            break
        if rng.random() < e.chance(state, char):
            inst = e.build(state, char, rng)
            if inst:
                out.append(offer(state, char, inst))
    return out


def lasting_answers(state, char):
    """Answers to the matters that follow from the people's state, for a character who
    is not the player (NPCs act on these without the year's chance events)."""
    out = []
    for kind in LASTING:
        d = EVENT_DEFS[kind]
        if d.chance(state, char) > 0:
            out += [ACTIONS[a] for a in d.answers if open_to(state, char, ACTIONS[a])]
    return out


def answer_key(event, action_id):
    """Plan entry for meeting a matter with one of its answers."""
    return f"a:{event.key}:{action_id}"


def taken_answers(event, plan):
    prefix = f"a:{event.key}:"
    return [k[len(prefix) :] for k in plan if k and k.startswith(prefix)]


def unmet(state):
    """Matters expected of the player that nothing in the plan answers."""
    return [e for e in state.events if e.expected and not taken_answers(e, state.plan)]


def resolve_events(state, plan):
    """Settle this year's matters given the year's plan. Returns (log lines, karma change).

    An expected matter is met by any of its answers (each carries its own karma);
    ignoring it costs its penalty.
    """
    rng = state.rng()
    notes = []
    karma = 0.0
    for event in state.events:
        event.data["taken_with"] = taken_answers(event, plan)
        taken = bool(event.data["taken_with"])
        if event.expected and not taken:
            karma -= event.penalty
        resolver = EVENT_DEFS[event.kind].resolve
        if resolver:
            note = resolver(state, event, taken, rng)
            if note:
                notes.append(note)
    return notes, karma
