"""Yearly events. Some are random, some grow out of the people's state, and several
place an obligation on the player. Ignoring an obligation costs karma; meeting
it guarantees nothing. Outcomes are deliberately not fair.
"""

from dataclasses import dataclass

from sankhara.sim import discoveries
from sankhara.sim.nation import adjust_settlements, refresh_averages
from sankhara.sim.people import die, family_of
from sankhara.sim.peoples import raid_chance
from sankhara.sim.state import EventInstance
from sankhara.sim.world import camp_tiles, is_watery

HUNGER_THRESHOLD = 0.05  # a shortfall bigger than this share of need is felt as hunger


@dataclass(frozen=True)
class EventDef:
    kind: str
    chance: object  # (state, char) -> probability this year
    build: object  # (state, char, rng) -> EventInstance | None, applying immediate effects
    resolve: object = None  # (state, event, taken, rng) -> str | None


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
    return EventInstance("flood", f"The water rose around {s.name} and swept shelters away.", s.id)


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


def _hunger(state, char, rng):
    hungry = [s.name for s in state.settlements.values() if _short(s)]
    if _is_leader(char) and state.nation.stores.get("food") >= 20:
        obligation = "open_stores"
    elif not _is_leader(char) and char.means.get("food") > 6:
        obligation = "share_food"
    else:
        obligation = None
    text = f"People are going hungry in {', '.join(hungry)}."
    if obligation:
        text += " What you have could help."
    return EventInstance("hunger", text, obligation=obligation, penalty=0.1)


def _short(s):
    return s.food_balance < -HUNGER_THRESHOLD * s.population * 0.1


def _discord(state, char, rng):
    obligation = "settle_quarrels" if _is_leader(char) else None
    text = "The camps are full of quarrels and old grudges."
    if obligation:
        text += " Everyone is waiting for you to do something."
    return EventInstance("discord", text, obligation=obligation, penalty=0.07)


def _discord_resolve(state, event, taken, rng):
    if not taken:
        adjust_settlements(state, cohesion=-4)
        return "The quarrels festered."
    return None


def _feud(state, char, rng):
    from sankhara.entities.namer import make_family_name

    a = make_family_name(state.nation.culture, rng)
    b = make_family_name(state.nation.culture, rng)
    if _is_leader(char):
        obligation = "judge_feud"
    elif rng.random() < 0.5:
        obligation = "make_peace"
    else:
        obligation = None
    text = f"The {a} and {b} families are at each other's throats over a broken promise."
    if obligation == "make_peace":
        text += " You know both families well."
    return EventInstance("feud", text, obligation=obligation, penalty=0.06, data={"a": a, "b": b})


def _feud_resolve(state, event, taken, rng):
    if taken and rng.random() < 0.8:
        return f"The {event.data['a']} and {event.data['b']} families made their peace."
    if rng.random() < 0.4:
        state.seat.population = max(12.0, state.seat.population - 1)
        adjust_settlements(state, cohesion=-3)
        return f"A man of the {event.data['a']} family was killed. Nobody will say who did it."
    adjust_settlements(state, cohesion=-1)
    return f"The {event.data['a']} and {event.data['b']} families no longer speak."


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
    obligation = "answer_raid" if _is_leader(char) else None
    text = f"The {n.name} raided {camp.name} by night, took food and left people dead."
    if obligation:
        text += " The people are looking to you."
    return EventInstance(
        "raid",
        text,
        camp.id,
        obligation=obligation,
        penalty=0.06,
        data={"neighbour": n.id, "also": ["avenge_raid"]},
    )


def _raid_resolve(state, event, taken, rng):
    n = state.neighbour(event.data.get("neighbour"))
    if n is None:
        return None
    if "answer_raid" in event.data.get("taken_with", []):
        if rng.random() < 0.55 + 0.4 * n.relations:
            n.relations = min(1.0, n.relations + 0.2)
            return f"The {n.name} sent back some of what they took, and gifts besides."
        return f"The {n.name} laughed at our messengers."
    if not taken:
        adjust_settlements(state, cohesion=-3)
        return "Nothing was done about the raid. People talk of little else."
    return None


def _beast(state, char, rng):
    can = char.station in ("leader", "hunter")
    text = "A great cat has been taking people at the edge of the camps."
    return EventInstance("beast", text, obligation="hunt_beast" if can else None, penalty=0.05)


def _beast_resolve(state, event, taken, rng):
    if taken and rng.random() < 0.7:
        state.player.means.add({"regard": 3})
        return "The cat was hunted down and its skin hung by the fire."
    if taken and rng.random() < 0.3:
        state.player.health -= 20
        return "The cat was killed, but it mauled you first."
    state.seat.population = max(12.0, state.seat.population - rng.randint(1, 3))
    return "The cat took more people before it moved on."


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
        "stranger",
        "A stranger came to your fire at dusk, alone and half-starved.",
        obligation="welcome_stranger",
        penalty=0.05,
    )


def _stranger_resolve(state, event, taken, rng):
    if taken and rng.random() < 0.12:
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
        obligation="search",
        penalty=0.05,
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
        "dying_elder",
        f"Old {who.full_name} is dying and asks for you.",
        target_id=who.id,
        obligation="sit_with_dying",
        penalty=0.04,
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
        obligation="tend_relative",
        penalty=0.08,
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
        obligation="tend_relative",
        penalty=0.04,
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


EVENTS = [
    EventDef("lean_year", lambda s, c: 0.09, _lean_year),
    EventDef("rich_year", lambda s, c: 0.09, _rich_year),
    EventDef("sickness", lambda s, c: 0.035, _sickness),
    EventDef("flood", lambda s, c: 0.04, _flood),
    EventDef("omen", lambda s, c: 0.03, _omen),
    EventDef("spark", lambda s, c: 0.08, _spark),
    EventDef(
        "hunger",
        lambda s, c: 0.85 if any(_short(x) for x in s.settlements.values()) else 0.0,
        _hunger,
    ),
    EventDef(
        "discord",
        lambda s, c: 0.5 if s.nation.cohesion < 35 else 0.0,
        _discord,
        _discord_resolve,
    ),
    EventDef(
        "feud",
        lambda s, c: 0.04 + (0.08 if s.nation.cohesion < 45 else 0.0),
        _feud,
        _feud_resolve,
    ),
    EventDef(
        "raid",
        lambda s, c: max((raid_chance(s, n) for n in s.neighbours.values()), default=0.0),
        _raid,
        _raid_resolve,
    ),
    EventDef("beast", lambda s, c: 0.04, _beast, _beast_resolve),
    EventDef("stranger", lambda s, c: 0.07, _stranger, _stranger_resolve),
    EventDef("lost_child", lambda s, c: 0.04, _lost_child, _lost_child_resolve),
    EventDef("dying_elder", lambda s, c: 0.06, _dying_elder),
    EventDef("relative_ill", lambda s, c: 0.12 * c.family_stability, _relative_ill, _ill_resolve),
    EventDef("sick_neighbour", lambda s, c: 0.07, _sick_neighbour, _ill_resolve),
    EventDef("illness", lambda s, c: 0.06, _illness),
    EventDef("injury", lambda s, c: 0.04, _injury),
    EventDef("windfall", lambda s, c: 0.04, _windfall),
    EventDef("theft", lambda s, c: 0.03, _theft),
]
EVENT_DEFS = {e.kind: e for e in EVENTS}
WHOLE_PEOPLE = {
    "lean_year",
    "rich_year",
    "sickness",
    "flood",
    "omen",
    "spark",
    "hunger",
    "discord",
    "feud",
    "raid",
    "beast",
}
MAX_EVENTS = 4


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
                out.append(inst)
    return out


def obligation_key(index):
    """Plan entry for answering the event at this index of state.events."""
    return f"event:{index}"


def resolve_events(state, plan):
    """Settle this year's obligations given the year's plan. Returns (log lines, karma change).

    An obligation is met by choosing its event entry, by choosing the same action
    directly, or by one of the event's alternative answers (which carry their own
    karma).
    """
    rng = state.rng()
    notes = []
    karma = 0.0
    for i, event in enumerate(state.events):
        answers = {obligation_key(i), event.obligation, *event.data.get("also", [])}
        taken_with = [k for k in plan if k in answers]
        event.data["taken_with"] = [
            event.obligation if k == obligation_key(i) else k for k in taken_with
        ]
        if not event.obligation:
            continue
        taken = bool(taken_with)
        if not taken:
            karma -= event.penalty
        resolver = EVENT_DEFS[event.kind].resolve
        if resolver:
            note = resolver(state, event, taken, rng)
            if note:
                notes.append(note)
    return notes, karma
