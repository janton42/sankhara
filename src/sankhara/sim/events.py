"""Yearly events. Some are random, some grow out of the nation's state, and several
place an obligation on the player. Ignoring an obligation costs karma; meeting
it guarantees nothing. Outcomes are deliberately not fair.
"""

from dataclasses import dataclass

from sankhara.sim.nation import adjust_settlements
from sankhara.sim.people import die, family_of
from sankhara.sim.state import EventInstance


@dataclass(frozen=True)
class EventDef:
    kind: str
    chance: object  # (state, char) -> probability this year
    build: object  # (state, char, rng) -> EventInstance | None, applying immediate effects
    resolve: object = None  # (state, event, taken, rng) -> str | None


def _settlement_named(state, sid):
    s = state.settlement(sid)
    return s.name if s else "the town"


# --- national ----------------------------------------------------------------


def _drought(state, char, rng):
    state.modifiers["harvest"] = state.modifiers.get("harvest", 1.0) * 0.65
    return EventInstance("drought", "The rains failed. The harvest will be thin everywhere.")


def _good_harvest(state, char, rng):
    state.modifiers["harvest"] = state.modifiers.get("harvest", 1.0) * 1.25
    return EventInstance("good_harvest", "The seasons were kind; the granaries will be full.")


def _plague(state, char, rng):
    state.modifiers["plague"] = rng.uniform(0.04, 0.12)
    for c in state.living():
        c.health -= rng.uniform(0, 25)
    return EventInstance("plague", "A sickness moved through the towns, sparing no station.")


def _flood(state, char, rng):
    s = rng.choice(list(state.settlements.values()))
    if s.works.get("irrigation", 0):
        s.works["irrigation"] -= 1
    s.population *= 0.95
    state.modifiers[f"harvest:{s.id}"] = 0.7
    return EventInstance("flood", f"The river rose at {s.name} and took fields and channels.", s.id)


def _comet(state, char, rng):
    adjust_settlements(state, stability=rng.choice([-2, 2]))
    return EventInstance(
        "comet", "A comet hung in the sky for a month. Nobody could agree on what it meant."
    )


def _envoy(state, char, rng):
    state.nation.treasury.coin += 30
    return EventInstance(
        "envoy", "Envoys from beyond the mountains came bearing gifts for the throne."
    )


def _unrest(state, char, rng):
    obligation = "grievances" if char.station in ("ruler", "noble") else None
    text = "Crowds gathered in the streets, angry and unheard."
    if obligation:
        text += " People expect you to do something."
    return EventInstance("unrest", text, obligation=obligation, penalty=0.08)


def _unrest_resolve(state, event, taken, rng):
    if not taken:
        adjust_settlements(state, stability=-4)
        return "The crowds were left to their anger."
    return None


def _famine(state, char, rng):
    hungry = [s.name for s in state.settlements.values() if s.food_balance < 0]
    if char.station == "ruler":
        obligation = "relieve"
    elif char.household.food > 5:
        obligation = "share_food"
    else:
        obligation = None
    text = f"People are going hungry in {', '.join(hungry)}."
    if obligation:
        text += " What you have could help."
    return EventInstance("famine", text, obligation=obligation, penalty=0.1)


def _bandits(state, char, rng):
    adjust_settlements(state, prosperity=-3)
    if char.station == "merchant":
        char.household.goods *= 0.8
    obligation = "watchmen" if char.station == "ruler" else None
    return EventInstance(
        "bandits",
        "Bandits are robbing travellers on the roads.",
        obligation=obligation,
        penalty=0.05,
    )


# --- local -------------------------------------------------------------------


def _fire(state, char, rng):
    s = state.settlement(char.settlement_id)
    s.population *= 0.97
    adjust_settlements(state, stability=-2, only=s.id)
    char.household.goods *= 0.7
    obligation = "rebuild" if char.station != "ruler" else None
    return EventInstance(
        "fire", f"Fire swept through part of {s.name}.", s.id, obligation=obligation, penalty=0.05
    )


def _neighbours(state, char):
    family = {c.id for _, c in family_of(state, char)}
    return [
        c
        for c in state.living()
        if c.settlement_id == char.settlement_id and not c.is_player and c.id not in family
    ]


def _sick_neighbour(state, char, rng):
    near = _neighbours(state, char)
    if not near:
        return None
    n = rng.choice(near)
    n.health -= 20
    return EventInstance(
        "sick_neighbour",
        f"Your neighbour {n.full_name} has fallen ill and has no one to look after them.",
        target_id=n.id,
        obligation="tend_relative",
        penalty=0.04,
    )


def _ill_resolve(state, event, taken, rng):
    target = state.character(event.target_id)
    if not target or not target.alive:
        return None
    chance = 0.2 if taken else 0.45
    if rng.random() < chance:
        die(state, target, "illness")
        return f"{target.full_name} died." + (" You did all you could." if taken else "")
    if not taken:
        target.adjust_affinity(state.player_id, -0.3)
        return f"{target.full_name} recovered, no thanks to you."
    return f"{target.full_name} recovered."


def _stranger(state, char, rng):
    return EventInstance(
        "stranger",
        "A stranger arrived at dusk, cold and asking for shelter.",
        obligation="shelter",
        penalty=0.05,
    )


def _stranger_resolve(state, event, taken, rng):
    if taken and rng.random() < 0.15:
        player = state.player
        player.household.coin *= 0.8
        return "In the morning the stranger was gone, and so was some of your coin."
    return None


def _good_season(state, char, rng):
    s = state.settlement(char.settlement_id)
    state.modifiers[f"harvest:{s.id}"] = state.modifiers.get(f"harvest:{s.id}", 1.0) * 1.15
    return EventInstance(
        "good_season", f"Around {s.name} the fields have never looked better.", s.id
    )


# --- family ------------------------------------------------------------------


def _family_members(state, char):
    return [c for _, c in family_of(state, char)]


def _relative_ill(state, char, rng):
    fam = _family_members(state, char)
    if not fam:
        return None
    target = rng.choice(fam)
    target.health -= 20
    rel = next(r for r, c in family_of(state, char) if c.id == target.id).lower()
    return EventInstance(
        "relative_ill",
        f"Your {rel} {target.name} has fallen seriously ill.",
        target_id=target.id,
        obligation="tend_relative",
        penalty=0.08,
    )


def _relative_debt(state, char, rng):
    adults = [c for c in _family_members(state, char) if c.age(state.year) >= 18]
    if not adults or char.household.coin < 5:
        return None
    target = rng.choice(adults)
    return EventInstance(
        "relative_debt",
        f"{target.name} has fallen into debt and asks you for help.",
        target_id=target.id,
        obligation="settle_debt",
        penalty=0.05,
    )


def _debt_resolve(state, event, taken, rng):
    target = state.character(event.target_id)
    if not taken and target and target.alive:
        target.adjust_affinity(state.player_id, -0.3)
        target.health -= 5
        return f"{target.name} had to manage without you."
    return None


# --- personal ------------------------------------------------------------------


def _illness(state, char, rng):
    char.health -= 15
    return EventInstance("illness", "You fell ill for much of the winter.")


def _windfall(state, char, rng):
    amount = 10 if char.station != "ruler" else 40
    char.household.coin += amount
    return EventInstance("windfall", "An old debt was unexpectedly repaid to you.")


def _theft(state, char, rng):
    char.household.coin *= 0.6
    return EventInstance("theft", "Thieves broke in and took a good part of your coin.")


def _injury(state, char, rng):
    char.health -= 10
    return EventInstance("injury", "A bad fall left you limping for months.")


EVENTS = [
    EventDef("drought", lambda s, c: 0.08, _drought),
    EventDef("good_harvest", lambda s, c: 0.1, _good_harvest),
    EventDef("plague", lambda s, c: 0.03, _plague),
    EventDef("flood", lambda s, c: 0.05, _flood),
    EventDef("comet", lambda s, c: 0.03, _comet),
    EventDef("envoy", lambda s, c: 0.05 if c.station == "ruler" else 0.0, _envoy),
    EventDef(
        "unrest", lambda s, c: 0.5 if s.nation.stability < 35 else 0.0, _unrest, _unrest_resolve
    ),
    EventDef(
        "famine",
        lambda s, c: 0.8 if any(x.food_balance < 0 for x in s.settlements.values()) else 0.0,
        _famine,
    ),
    EventDef("bandits", lambda s, c: 0.05 + (0.1 if s.nation.stability < 45 else 0.0), _bandits),
    EventDef("fire", lambda s, c: 0.04, _fire),
    EventDef("sick_neighbour", lambda s, c: 0.1, _sick_neighbour, _ill_resolve),
    EventDef("stranger", lambda s, c: 0.1, _stranger, _stranger_resolve),
    EventDef("good_season", lambda s, c: 0.07, _good_season),
    EventDef("relative_ill", lambda s, c: 0.14 * c.family_stability, _relative_ill, _ill_resolve),
    EventDef(
        "relative_debt", lambda s, c: 0.06 * c.family_stability, _relative_debt, _debt_resolve
    ),
    EventDef("illness", lambda s, c: 0.07, _illness),
    EventDef("windfall", lambda s, c: 0.05, _windfall),
    EventDef("theft", lambda s, c: 0.04, _theft),
    EventDef("injury", lambda s, c: 0.04, _injury),
]
EVENT_DEFS = {e.kind: e for e in EVENTS}
NATIONAL = {
    "drought",
    "good_harvest",
    "plague",
    "flood",
    "comet",
    "envoy",
    "unrest",
    "famine",
    "bandits",
}
MAX_EVENTS = 4


def generate_events(state, char, national_only=False):
    """Roll this year's events, applying their immediate effects."""
    rng = state.rng()
    out = []
    for e in EVENTS:
        if national_only and e.kind not in NATIONAL:
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

    An obligation is met by choosing its event entry, or by choosing the same
    action directly (e.g. a ruler opening the stores during a famine).
    """
    rng = state.rng()
    notes = []
    karma = 0.0
    for i, event in enumerate(state.events):
        if not event.obligation:
            continue
        taken = obligation_key(i) in plan or event.obligation in plan
        if not taken:
            karma -= event.penalty
        resolver = EVENT_DEFS[event.kind].resolve
        if resolver:
            note = resolver(state, event, taken, rng)
            if note:
                notes.append(note)
    return notes, karma
