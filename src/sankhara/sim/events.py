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

import math
from dataclasses import dataclass

from sankhara.sim import discoveries, say, tendencies
from sankhara.sim.actions import ACTIONS, LOAN, could_lead, keeps_marks, leads_with_shares, open_to
from sankhara.sim.nation import adjust_settlements, people_scale, refresh_averages
from sankhara.sim.people import (
    LEADER_AGE,
    ally,
    die,
    family_of,
    feels,
    grudge,
    grudge_key,
    in_laws,
    leader_failing,
    members,
    pick_match,
    standing,
    support,
    wed,
)
from sankhara.sim.peoples import WALL_YEARS, raid_chance, wall_age
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


def _joined(state, a, b, rng):
    """A marriage ends a feud for good: the grudge is gone and the families warm to each
    other. If each has someone grown and unwed, they are the ones who marry."""
    ally(state, a, b)
    _estrange(state, a, b, -0.2)
    unwed = [
        [c for c in members(state, f) if c.spouse_id is None and not c.is_player] for f in (a, b)
    ]
    for one, other in ((unwed[0], unwed[1]), (unwed[1], unwed[0])):
        men = [c for c in one if c.gender == "male" and c.age(state.year) >= ADULT_AGE]
        women = [c for c in other if c.gender == "female" and c.age(state.year) >= ADULT_AGE]
        if men and women:
            man, woman = rng.choice(men), rng.choice(women)
            wed(state, man, woman)
            return (
                f"{man.full_name} and {woman.name} were wed, and the {a} and {b} families are kin."
            )
    return f"A son and daughter of the {a} and {b} families were wed, and the feud was ended."


def _estrange(state, a, b, amount):
    """Members of two families think worse of each other."""
    for x in members(state, a):
        for y in members(state, b):
            x.adjust_affinity(y.id, -amount)
            y.adjust_affinity(x.id, -amount)


def _feud_resolve(state, event, taken, rng):
    a, b = event.data["a"], event.data["b"]
    taken_with = set(event.data.get("taken_with", []))
    if "join_families" in taken_with:
        return _joined(state, a, b, rng)
    if "set_blood_price" in taken_with and rng.random() < 0.9:
        state.nation.grudges.pop(grudge_key(a, b), None)
        return f"The {b} family paid what was set, and the {a} family took it."
    if "ordeal" in taken_with:
        loser = rng.choice((a, b))
        for c in members(state, loser):
            c.adjust_affinity(state.player_id, -0.2)
        if rng.random() < 0.7:
            state.nation.grudges.pop(grudge_key(a, b), None)
            return f"The ordeal went against the {loser} family. They bowed to it, mostly."
        state.nation.grudges[grudge_key(a, b)] = state.year
        return f"The ordeal went against the {loser} family, and they would not accept it."
    peacemaking = {"judge_feud", "make_peace"} & taken_with
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
KIN_SLIGHTED = 0.1  # how much kin by marriage cool when their need is ignored
KIN_WARM = 0.1  # how warm kin must feel toward you to send help unasked
KIN_GIFT = 8
BARE_HEARTH = 15  # a family's food below which kin may send help
ENEMY = -0.4  # how ill someone must feel toward you to be an enemy
VENGEANCE = 0.3  # a year in which those owed blood come for it
MATCH_CHANCE = 0.3  # a year in which a family offers the unwed player a match
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


def _match_open(state, char):
    """Whether the player is grown, unwed and young enough to be offered a match."""
    return char.is_player and char.spouse_id is None and ADULT_AGE <= char.age(state.year) <= 40


def _match_build(state, char, rng):
    """A family offers the player a match: someone known if there is anyone fitting,
    otherwise someone of a family the player has had little to do with (who is only
    tracked once the match is taken)."""
    from sankhara.entities.namer import make_family_name, make_first_name

    match = pick_match(state, char, rng)
    if match is not None:
        name, family, age = match.name, match.family_name, match.age(state.year)
        target = match.id
    else:
        gender = "female" if char.gender == "male" else "male"
        name = make_first_name(state.nation.culture, gender, rng)
        family = make_family_name(state.nation.culture, rng)
        age = max(ADULT_AGE, char.age(state.year) + rng.randint(-5, 5))
        target = None
    return EventInstance(
        "match",
        f"The {family} family would see you wed to {name}, aged {age}.",
        target_id=target,
        data={"match": name, "family": family, "age": age},
    )


def _kin_asks_build(state, char, rng):
    kin = in_laws(state, char)
    if not kin:
        return None
    family, _ = rng.choice(kin)
    return EventInstance(
        "kin_asks",
        f"Your kin by marriage, the {family} family, are short of food and ask you for help.",
        data={"family": family},
    )


def _kin_asks_resolve(state, event, taken, rng):
    if taken:
        return None
    family = event.data["family"]
    for c in members(state, family):
        c.adjust_affinity(state.player_id, -KIN_SLIGHTED)
    return f"The {family} family waited for help from you that never came."


def _kin_warmth(state, char, kin):
    return sum(feels(state, c, char) for c in kin) / len(kin)


def _hearth_bare(state, char):
    camp = state.settlement(char.settlement_id)
    return char.means.get("food") < BARE_HEARTH or (camp is not None and _short(camp))


def _kin_help_build(state, char, rng):
    """Kin by marriage who think well of you send food when your hearth is bare."""
    kin = [(f, k) for f, k in in_laws(state, char) if _kin_warmth(state, char, k) > KIN_WARM]
    if not kin:
        return None
    family, _ = rng.choice(kin)
    char.means.add({"food": KIN_GIFT})
    return EventInstance(
        "kin_help", f"The {family} family, your kin by marriage, sent food to your hearth."
    )


def _divided_build(state, char, rng):
    r = state.character(state.nation.divided) if state.nation.divided else None
    leader = state.leader
    if r is None or not r.alive or leader is None or r is leader:
        return None
    if char is r:
        text = f"The people are divided between {leader.name}, who leads them, and you."
    elif char is leader:
        text = f"The people are divided: many would rather follow {r.full_name}."
    else:
        text = f"The people are divided between {leader.name} and {r.full_name}."
    return EventInstance(
        "divided", text, target_id=r.id, data={"rival": r.name, "leader": leader.name}
    )


def _divided_resolve(state, event, taken, rng):
    if taken or not event.expected:
        return None
    adjust_settlements(state, cohesion=-2)
    return "The camps went on apart, and no one went between them."


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
    taken_with = event.data.get("taken_with", [])
    welcomed = "welcome_stranger" in taken_with
    if welcomed and rng.random() < 0.12:
        state.player.means.set("food", state.player.means.get("food") * 0.7)
        return "In the morning the stranger was gone, and so was some of your food."
    if say.has_say(state, state.player):
        return None
    # others decide; the player's word carries by their standing
    deciders = [c for c in say.deciders_of(state, state.player.settlement_id) if not c.is_player]
    lean = sum(
        tendencies.affinity(c.tendencies, ("generous", "caring"))
        - tendencies.affinity(c.tendencies, ("harsh", "acquisitive"))
        for c in deciders
    ) / max(1, len(deciders))
    voice = min(0.4, 0.1 + state.player.means.get("regard") / 100)
    if "speak_for_stranger" in taken_with:
        lean += voice
    elif "speak_against_stranger" in taken_with:
        lean -= voice
    who = deciders_word(deciders)
    if rng.random() < 0.5 + lean:
        if rng.random() < 0.35:
            options = discoveries.available(state)
            if options:
                discoveries.add_insight(state, rng.choice(options).id, 15)
        return f"{who} took the stranger in."
    return f"{who} sent the stranger on."


def deciders_word(deciders):
    if not deciders:
        return "The people"
    if len(deciders) == 1:
        return deciders[0].full_name
    return "The elders" if all(c.is_elder for c in deciders) else "Those who decide"


def _newcomers(state, char, rng):
    camp = state.settlement(char.settlement_id) or state.seat
    met = [n for n in state.neighbours.values() if n.met]
    people = rng.choice(met).name if met and rng.random() < 0.5 else ""
    whence = f"of the {people}" if people else "from far off"
    return EventInstance(
        "newcomers",
        f"A family {whence} asks to settle at {camp.name}.",
        settlement_id=camp.id,
        data={"people": people, "camp": camp.name},
    )


def _in_town(state, char):
    camp = state.settlement(char.settlement_id)
    return camp is not None and camp.kind == "town"


def _market_traders(state, char, rng):
    met = [n for n in state.neighbours.values() if n.met and n.relations > -0.5]
    if not met:
        return None
    n = rng.choice(met)
    camp = state.settlement(char.settlement_id)
    return EventInstance(
        "market_traders",
        f"Traders of the {n.name} have laid out their goods in the market at {camp.name}.",
        settlement_id=camp.id,
        data={"people": n.name, "camp": camp.name},
    )


MIDDEN_SICKNESS = 0.6  # the chance a town whose middens are left brings on a sickness


def _middens(state, char, rng):
    camp = state.settlement(char.settlement_id)
    return EventInstance(
        "middens",
        f"The middens of {camp.name} have crept up to the houses, and the water tastes of them.",
        settlement_id=camp.id,
        data={"camp": camp.name},
    )


def _middens_resolve(state, event, taken, rng):
    camp = state.settlement(event.settlement_id)
    if camp is None:
        return None
    taken_with = event.data.get("taken_with", [])
    if "have_middens_cleared" in taken_with:
        return None
    # others with a say may see to it, as they are inclined
    deciders = [c for c in say.deciders_of(state, camp.id) if not c.is_player]
    if any(rng.random() < 0.3 + tendencies.affinity(c.tendencies, ("caring",)) for c in deciders):
        return f"{deciders_word(deciders)} set the families of {camp.name} to clear the middens."
    chance = MIDDEN_SICKNESS * (0.5 if "clear_own_midden" in taken_with else 1.0)
    if rng.random() >= chance:
        return None
    camp.population *= 1 - rng.uniform(0.02, 0.06)
    for c in state.living():
        if c.settlement_id == camp.id:
            c.health -= rng.uniform(0, 15)
    return f"A flux went through the houses of {camp.name}."


def _others_near(state, char):
    """Grown people of other families in the player's camp."""
    return [
        c
        for c in _neighbours_of(state, char)
        if c.family_name != char.family_name and c.age(state.year) >= ADULT_AGE
    ]


def _unguarded(state, char, rng):
    near = _others_near(state, char)
    if not near:
        return None
    who = rng.choice(near)
    return EventInstance(
        "unguarded",
        f"The {who.family_name} family have gone to the gathering, and left their stores "
        "unguarded.",
        target_id=who.id,
        data={"family": who.family_name},
    )


def _insult(state, char, rng):
    near = _others_near(state, char)
    if not near:
        return None
    weights = [math.exp(-3 * feels(state, c, char)) for c in near]
    who = rng.choices(near, weights)[0]
    return EventInstance(
        "insult",
        f"{who.full_name} mocked you before everyone at the fire.",
        target_id=who.id,
        data={"family": who.family_name},
    )


def _desire(state, char, rng):
    near = [
        c
        for c in _others_near(state, char)
        if c.gender != char.gender
        and abs(c.age(state.year) - char.age(state.year)) <= 15
        and (c.spouse_id is not None or char.spouse_id is not None)
    ]
    if not near:
        return None
    who = rng.choice(near)
    whose = state.character(who.spouse_id)
    who_text = f"{who.full_name}, {whose.name}'s mate," if whose else who.full_name
    return EventInstance(
        "desire",
        f"{who_text} seeks your company whenever no one else is near.",
        target_id=who.id,
        data={"family": who.family_name},
    )


def _enemies(state, char):
    return [
        c
        for c in state.living()
        if not c.is_player
        and c.age(state.year) >= ADULT_AGE
        and c.id not in {k.id for _, k in family_of(state, char)}
        and feels(state, c, char) <= ENEMY
    ]


def _enemy_alone(state, char, rng):
    foes = _enemies(state, char)
    if not foes:
        return None
    who = min(foes, key=lambda c: feels(state, c, char))
    return EventInstance(
        "enemy_alone",
        f"{who.full_name}, who bears you nothing but ill will, goes alone to the river at dawn.",
        target_id=who.id,
        data={"family": who.family_name},
    )


def _owed_by(state, char):
    return [
        (family, victim)
        for family, (killer, victim) in state.nation.blood_owed.items()
        if killer == char.id and members(state, family)
    ]


def _blood_owed(state, char, rng):
    owed = _owed_by(state, char)
    if not owed:
        return None
    family, victim = owed[0]
    return EventInstance(
        "blood_owed",
        f"The {family} family say blood is owed for {victim}.",
        data={"family": family, "victim": victim},
    )


def _blood_owed_resolve(state, event, taken, rng):
    family = event.data["family"]
    if family not in state.nation.blood_owed:
        return None
    taken_with = event.data.get("taken_with", [])
    player = state.player
    if "flee" in taken_with and rng.random() < 0.6:
        return f"The {family} family did not follow you."
    if rng.random() >= VENGEANCE:
        return None
    if "stand_ground" in taken_with and rng.random() < 0.6:
        player.health = max(1.0, player.health - 35)
        state.nation.blood_owed.pop(family, None)
        return f"Men of the {family} family came for you, and you were ready. You live, barely."
    state.nation.blood_owed.pop(family, None)
    player.doom = f"the {family} family's vengeance"
    return f"Men of the {family} family came for you in the night."


def _outshone(state, char, rng):
    """Someone of another family is rising past you, and they are no friend of yours."""
    near = [
        c
        for c in _others_near(state, char)
        if c.means.get("regard") > char.means.get("regard") and feels(state, c, char) < 0.2
    ]
    if not near:
        return None
    who = max(near, key=lambda c: c.means.get("regard"))
    return EventInstance(
        "outshone",
        f"People look more and more to {who.full_name}, and less to you.",
        target_id=who.id,
        data={"family": who.family_name},
    )


def _trade_offer(state, char, rng):
    near = _others_near(state, char)
    if not near:
        return None
    who = rng.choice(near)
    return EventInstance(
        "trade_offer",
        f"{who.full_name} wants to trade with you, and has never been good at counting.",
        target_id=who.id,
        data={"family": who.family_name},
    )


def _asks_loan(state, char, rng):
    """Someone of another family whose hearth is bare asks to borrow from you."""
    poor = [c for c in _others_near(state, char) if c.means.get("food") < BARE_HEARTH]
    if not poor or char.means.get("food") < 1.5 * LOAN:
        return None
    who = rng.choice(poor)
    return EventInstance(
        "asks_loan",
        f"{who.full_name} asks to borrow food from you until the harvests turn.",
        target_id=who.id,
        data={"family": who.family_name},
    )


def _owed_to(state, char):
    """Debts owed to this character that have fallen due; debts of the dead are gone."""
    nation = state.nation
    nation.debts = [d for d in nation.debts if _alive(state, d["by"]) and _alive(state, d["to"])]
    return [d for d in nation.debts if d["to"] == char.id and d["due"] <= state.year]


def _alive(state, cid):
    who = state.character(cid)
    return who is not None and who.alive


def _debt_due(state, char, rng):
    debt = _owed_to(state, char)[0]
    who = state.character(debt["by"])
    data = {"family": who.family_name, "by": who.id}
    if who.means.get("food") >= debt["food"] + BARE_HEARTH:
        who.means.add({"food": -debt["food"]})
        char.means.add({"food": debt["food"]})
        state.nation.debts.remove(debt)
        data["repaid"] = True
        return EventInstance(
            "debt_due",
            f"{who.full_name} has given back what they owed you.",
            target_id=who.id,
            data=data,
        )
    return EventInstance(
        "debt_due",
        f"What {who.full_name} owes you has fallen due, and they cannot give it back.",
        target_id=who.id,
        data=data,
    )


GROUNDS = ("the ground by the stream", "the far grove", "the old hunting run", "the clay pit")


def _false_mark(state, char, rng):
    """A family wants its claim set down in marks, though the ground is another's."""
    families = sorted({c.family_name for c in _others_near(state, char)})
    if len(families) < 2:
        return None
    family, other = rng.sample(families, 2)
    ground = rng.choice(GROUNDS)
    return EventInstance(
        "false_mark",
        f"The {family} family ask you to set down in marks that {ground} is theirs, "
        f"though it has always been the {other} family's.",
        data={"family": family, "other": other},
    )


def _wall_crumbling(state, char, rng):
    decides = say.has_say(state, char)
    leader = state.leader
    if decides:
        text = "The wall is crumbling, and it will take every family's hands to mend it."
    elif leader is not None:
        text = f"{leader.full_name} has called every family to send hands to mend the wall."
    else:
        text = "The call has gone out for every family to send hands to mend the wall."
    return EventInstance("wall_crumbling", text, data={"decides": decides})


def _wall_resolve(state, event, taken, rng):
    if not event.data.get("decides"):
        state.nation.walls_mended = state.year  # the others mend it, whatever you do
    return None


def _shares_in(state, char, rng):
    return EventInstance(
        "shares_in",
        "The families' shares have come in to your store, more than your own hearth needs.",
    )


def _share_due(state, char, rng):
    leader = state.leader
    if leader is None or leader.family_name == char.family_name:
        return None
    return EventInstance(
        "share_due",
        f"Your family's share is due at {leader.full_name}'s store.",
        target_id=leader.id,
        data={"family": leader.family_name},
    )


def _share_resolve(state, event, taken, rng):
    leader = state.character(event.target_id)
    if not taken and leader is not None:
        leader.adjust_affinity(state.player_id, -0.05)
    return None


def _claim(kind, text):
    """A role matter about what is whose, with a known family of the player's camp."""

    def build(state, char, rng):
        near = [c for c in _neighbours_of(state, char) if c.family_name != char.family_name]
        if not near:
            return None
        who = rng.choice(near)
        family = who.family_name
        return EventInstance(
            kind, text.format(family=family), target_id=who.id, data={"family": family}
        )

    return build


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
        answers=("open_stores", "share_food", "bring_food", "keep_close", "keep_seed"),
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
        "match",
        lambda s, c: MATCH_CHANCE if _match_open(s, c) else 0.0,
        _match_build,
        answers=("accept_match", "bride_price", "refuse_match"),
    ),
    EventDef(
        "kin_asks",
        lambda s, c: (0.4 if _hungry(s) else 0.06) if c.is_player and in_laws(s, c) else 0.0,
        _kin_asks_build,
        _kin_asks_resolve,
        answers=("share_with_kin", "refuse_kin"),
        expects=("share_with_kin", "refuse_kin"),
        penalty=0.04,
    ),
    EventDef(
        "kin_help",
        lambda s, c: 0.5 if c.is_player and _hearth_bare(s, c) else 0.0,
        _kin_help_build,
    ),
    EventDef(
        "divided",
        lambda s, c: 0.7 if s.nation.divided else 0.0,
        _divided_build,
        _divided_resolve,
        answers=(
            "hear_them_out",
            "make_room",
            "face_down",
            "back_rival",
            "back_leader",
            "stand_forward",
            "stay_out",
        ),
        expects=("hear_them_out", "make_room", "face_down"),
        penalty=0.05,
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
        answers=(
            "judge_feud",
            "set_blood_price",
            "ordeal",
            "make_peace",
            "join_families",
            "side_with",
        ),
        expects=("judge_feud", "set_blood_price", "ordeal"),
        penalty=0.06,
    ),
    EventDef(
        "raid",
        lambda s, c: max((raid_chance(s, n) for n in s.neighbours.values()), default=0.0),
        _raid,
        _raid_resolve,
        answers=("answer_raid", "stand_guard", "avenge_raid", "take_captives", "help_camp"),
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
        "outshone",
        lambda s, c: 0.05,
        _outshone,
        answers=("spread_tale", "praise_them", "say_nothing"),
    ),
    EventDef(
        "trade_offer",
        lambda s, c: 0.06 if "exchange" in s.nation.known and c.station != "trader" else 0.0,
        _trade_offer,
        answers=("short_measure", "fair_trade"),
    ),
    # what grows with later ideas
    EventDef(
        "asks_loan",
        lambda s, c: 0.08 if "market" in s.nation.known else 0.0,
        _asks_loan,
        answers=("lend_food", "lend_for_more", "give_outright", "refuse_loan"),
    ),
    EventDef(
        "debt_due",
        lambda s, c: 1.0 if _owed_to(s, c) else 0.0,
        _debt_due,
        answers=("forgive_debt", "take_what_they_have", "work_off_debt", "wait_longer"),
    ),
    EventDef(
        "false_mark",
        lambda s, c: 0.12 if keeps_marks(s, c) else 0.0,
        _false_mark,
        answers=("mark_as_it_is", "mark_for_them", "mark_both_claims"),
    ),
    EventDef(
        "wall_crumbling",
        lambda s, c: 0.2 if wall_age(s) > WALL_YEARS * 0.8 else 0.0,
        _wall_crumbling,
        _wall_resolve,
        answers=(
            "call_levy",
            "levy_spare_kin",
            "ask_willing",
            "work_wall",
            "send_food_for_wall",
            "shirk_wall",
        ),
        expects=("call_levy", "levy_spare_kin", "ask_willing", "work_wall", "send_food_for_wall"),
        penalty=0.03,
    ),
    EventDef(
        "shares_in",
        lambda s, c: 0.15 if leads_with_shares(s, c) else 0.0,
        _shares_in,
        answers=("shares_to_stores", "keep_shares", "shares_to_needy"),
    ),
    EventDef(
        "share_due",
        lambda s, c: (
            0.1
            if s.nation.known.get("tribute") == "leaders_share" and c.station != "leader"
            else 0.0
        ),
        _share_due,
        _share_resolve,
        answers=("pay_share", "hide_share"),
        expects=("pay_share",),
        penalty=0.02,
    ),
    EventDef(
        "unguarded",
        lambda s, c: 0.05,
        _unguarded,
        answers=("steal_stores", "leave_stores", "guard_stores"),
    ),
    EventDef(
        "insult",
        lambda s, c: 0.06,
        _insult,
        answers=("strike", "answer_back", "let_pass"),
    ),
    EventDef(
        "desire",
        lambda s, c: 0.04,
        _desire,
        answers=("affair", "keep_away"),
    ),
    EventDef(
        "enemy_alone",
        lambda s, c: 0.08 if c.is_player and _enemies(s, c) else 0.0,
        _enemy_alone,
        answers=("kill", "confront", "let_be"),
    ),
    EventDef(
        "blood_owed",
        lambda s, c: 0.9 if c.is_player and _owed_by(s, c) else 0.0,
        _blood_owed,
        _blood_owed_resolve,
        answers=("pay_blood_price", "flee", "stand_ground"),
    ),
    EventDef(
        "newcomers",
        lambda s, c: 0.08 if say.scale(s) == "town" and say.has_say(s, c) else 0.0,
        _newcomers,
        answers=("take_in_family", "turn_away_family"),
        expects=("take_in_family", "turn_away_family"),
        penalty=0.03,
    ),
    # what comes with a town
    EventDef(
        "market_traders",
        lambda s, c: 0.1 if "market" in s.nation.known and _in_town(s, c) else 0.0,
        _market_traders,
        answers=("trade_with_strangers", "cheat_strangers", "ask_far_lands", "toll_traders"),
    ),
    EventDef(
        "middens",
        lambda s, c: 0.08 if _in_town(s, c) else 0.0,
        _middens,
        _middens_resolve,
        answers=("have_middens_cleared", "clear_own_midden"),
        expects=("have_middens_cleared",),
        penalty=0.03,
    ),
    EventDef(
        "grove",
        _role("gatherer", chance=0.15),
        _claim("grove", "The {family} family say the nut grove near the camp is theirs alone."),
        answers=("share_grove", "gather_anyway", "leave_grove"),
    ),
    EventDef(
        "traps",
        _role("fisher", chance=0.15),
        _claim("traps", "Someone has been taking fish from your traps. You suspect the {family}s."),
        answers=("watch_traps", "set_more", "empty_theirs"),
    ),
    EventDef(
        "boundary",
        _role("planter", chance=0.15),
        _claim(
            "boundary",
            "The stones between your field and the {family} family's have been moved.",
        ),
        answers=("take_to_judgement", "move_further", "let_it_be"),
    ),
    EventDef(
        "stray",
        _role("herder", chance=0.15),
        _claim("stray", "A beast from the {family} family's herd has strayed into yours."),
        answers=("return_stray", "keep_stray", "ask_reward"),
    ),
    EventDef(
        "stranger",
        lambda s, c: 0.07 if say.scale(s) != "town" else 0.0,
        _stranger,
        _stranger_resolve,
        answers=("welcome_stranger", "send_on", "speak_for_stranger", "speak_against_stranger"),
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
LASTING = (
    "hunger",
    "discord",
    "low_stores",
    "plenty",
    "divided",
)  # matters that follow the people's state
MAX_EVENTS = 5


def offer(state, char, event):
    """Fill in which answers this character has, and whether the matter is expected of them."""
    d = EVENT_DEFS[event.kind]
    event.answers = [a for a in d.answers if open_to(state, char, ACTIONS[a])]
    event.expected = any(a in d.expects for a in event.answers)
    event.penalty = d.penalty if event.expected else 0.0
    if event.kind == "divided" and event.target_id == char.id:
        event.answers = [a for a in event.answers if a != "back_rival"]  # not for yourself
    if event.data.get("repaid"):
        event.answers = []  # news, not a matter
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
