"""Tracked characters: creating them, families, ageing, death, marriage, births and who
leads the people.

Only people who matter are tracked individually: the leader and their family, the
respected elders, the player's family and a few neighbours. Everyone else is the
camps' population figures.
"""

import math

from sankhara.entities.namer import make_family_name, make_first_name
from sankhara.sim import discoveries
from sankhara.sim.state import Budget, Character
from sankhara.sim.stations import ADULT_AGE, BAND_ROLES, STATIONS, rebirth_weights
from sankhara.sim.tendencies import random_tendencies

LIFESPAN_AFTER_ADULTHOOD = (20, 50)  # playable years of a life, before the hidden death
MARRIAGE_CHANCE = 0.25
BIRTH_CHANCE = 0.22
FERTILE_AGES = (17, 40)
MAX_CHILDREN = 6
ELDER_COUNT = 4
ELDER_AGE = 30
NEIGHBOUR_COUNT = 3
OUTSIDE_SPOUSE_CHANCE = 0.25  # once other peoples are met


def random_death_age(rng):
    return ADULT_AGE + rng.randint(*LIFESPAN_AFTER_ADULTHOOD)


def create_character(
    state,
    station,
    settlement_id,
    birth_year,
    *,
    gender=None,
    family_name=None,
    mother=None,
    father=None,
    tendencies=None,
    culture=None,
):
    rng = state.rng()
    culture = culture or state.nation.culture
    gender = gender or rng.choice(["male", "female"])
    if family_name is None:
        family_name = father.family_name if father else make_family_name(culture, rng)
    char = Character(
        id=state.new_id(),
        name=make_first_name(culture, gender, rng),
        family_name=family_name,
        gender=gender,
        birth_year=birth_year,
        death_age=random_death_age(rng),
        station=station,
        settlement_id=settlement_id,
        health=rng.uniform(70, 95),
        mother_id=mother.id if mother else None,
        father_id=father.id if father else None,
        means=Budget(dict(STATIONS[station].start)),
        tendencies=tendencies if tendencies is not None else random_tendencies(rng, 0.4),
    )
    for parent in (mother, father):
        if parent:
            parent.children.append(char.id)
            # friendships and grudges pass, in part, to the children
            for other, feeling in parent.affinity.items():
                known = state.character(int(other))
                if known and known.alive:
                    char.adjust_affinity(other, INHERITED_FEELING * feeling)
    return state.add_character(char)


# --- grudges between families -------------------------------------------------

GRUDGE_YEARS = 60  # how long a grudge is remembered if nothing renews it
GRUDGE_COOL = 0.4  # how much colder members of feuding families are to each other
INHERITED_FEELING = 0.25  # how much of each parent's feelings a child is born with


def grudge_key(a, b):
    return "|".join(sorted((a, b)))


def grudge(state, a, b):
    """Whether these two families bear each other a grudge."""
    if a == b:
        return False
    year = state.nation.grudges.get(grudge_key(a, b))
    return year is not None and state.year - year <= GRUDGE_YEARS


def grudges_of(state, family_name):
    """The families this one has fallen out with, as (other family, year) pairs."""
    out = []
    for key, year in state.nation.grudges.items():
        a, b = key.split("|")
        if family_name in (a, b) and grudge(state, a, b):
            out.append((b if a == family_name else a, year))
    return out


def feels(state, who, other):
    """How `who` feels toward `other`, counting what stands between their families."""
    feeling = who.feels(other.id)
    if grudge(state, who.family_name, other.family_name):
        feeling -= GRUDGE_COOL
    return max(-1.0, feeling)


def child_role(state, parent, rng):
    """Children mostly follow a parent's way of life; some find another."""
    if parent.station != "leader" and rng.random() < 0.75:
        return parent.station
    weights = {k: v for k, v in rebirth_weights(state.nation).items() if k != "leader"}
    return rng.choices(list(weights), list(weights.values()))[0]


def marry(a, b):
    a.spouse_id, b.spouse_id = b.id, a.id
    a.adjust_affinity(b.id, 0.3)
    b.adjust_affinity(a.id, 0.3)


def create_spouse(state, char):
    """A spouse for `char`: from among the people, or from a people they've met."""
    rng = state.rng()
    gender = "female" if char.gender == "male" else "male"
    age = max(ADULT_AGE, char.age(state.year) + rng.randint(-5, 5))
    friendly = [n for n in state.neighbours.values() if n.met and n.relations > -0.2]
    outsider = friendly and rng.random() < OUTSIDE_SPOUSE_CHANCE
    people = rng.choice(friendly) if outsider else None
    roles = [r for r in BAND_ROLES if r != "keeper"]
    spouse = create_character(
        state,
        char.station if char.station != "leader" else rng.choice(roles),
        char.settlement_id,
        state.year - age,
        gender=gender,
        culture=people.culture if people else None,
    )
    if people:
        spouse.origin = people.name
        people.relations = min(1.0, people.relations + 0.1)
    if char.gender == "male":
        spouse.family_name = char.family_name
    marry(char, spouse)
    return spouse


def family_of(state, char):
    """Living parents, spouse, children and siblings, as (relation, character) pairs."""
    out = []
    for rel, cid in (("Mother", char.mother_id), ("Father", char.father_id)):
        c = state.character(cid)
        if c and c.alive:
            out.append((rel, c))
    spouse = state.character(char.spouse_id)
    if spouse and spouse.alive:
        out.append(("Spouse", spouse))
    for cid in char.children:
        c = state.character(cid)
        if c and c.alive:
            out.append(("Son" if c.gender == "male" else "Daughter", c))
    for sib in siblings(state, char):
        out.append(("Brother" if sib.gender == "male" else "Sister", sib))
    return out


def members(state, family_name):
    """The living, tracked people of a family."""
    return [c for c in state.living() if c.family_name == family_name]


def siblings(state, char):
    parent = state.character(char.mother_id) or state.character(char.father_id)
    if not parent:
        return []
    return [
        state.character(cid)
        for cid in parent.children
        if cid != char.id and state.character(cid) and state.character(cid).alive
    ]


def is_tracked_lineage(state, char):
    """Whose marriages and children get tracked individually: the leader and their
    children, and the player's immediate family."""
    player = state.player
    leader_id = state.nation.leader_id
    return (
        char.id == leader_id
        or leader_id in (char.mother_id, char.father_id)
        or char.id in (player.id, player.spouse_id, player.mother_id, player.father_id)
    )


def die(state, char, cause):
    char.alive = False
    char.death_year = state.year
    char.cause_of_death = cause
    char.is_elder = False
    spouse = state.character(char.spouse_id)
    if spouse and spouse.alive:
        spouse.spouse_id = None
    # their own undertakings end with them; the people's works pass on (game._world_year)
    for project in state.projects_of(char.id):
        if not char.is_player and not project.common:
            del state.projects[str(project.id)]


def age_and_health(state, char, rng):
    """Yearly drift in health. Returns a cause of death, or '' if they live on."""
    age = char.age(state.year)
    if age > 30:
        char.health -= 0.6 + max(0, age - 50) * 0.15
    char.health += rng.uniform(-2, 2.5) + discoveries.fx(state, "health") * 0.3
    char.health = max(0.0, min(100.0, char.health))
    if age >= char.death_age:
        if age >= 55:
            return "old age"
        return rng.choice(["a sudden fever", "a fall", "a wasting sickness", "a wound gone bad"])
    if char.health <= 0:
        return "failing health"
    return ""


def yearly_lifecycle(state, protect=()):
    """Ageing, deaths, marriages and births for all tracked characters.

    `protect` holds ids that cannot die this year (the player's childhood).
    Returns log lines about people the player would notice.
    """
    rng = state.rng()
    notes = []
    player = state.player
    near = {cid for cid in (player.mother_id, player.father_id, player.spouse_id) if cid}
    near.update(player.children)
    near.add(state.nation.leader_id)

    for char in list(state.living()):
        if char.is_player or char.id in protect:
            continue
        cause = age_and_health(state, char, rng)
        if cause:
            die(state, char, cause)
            if char.id in near:
                notes.append(f"{char.full_name} died of {cause}.")

    for char in list(state.living()):
        age = char.age(state.year)
        if char.is_player or age < ADULT_AGE:
            continue
        if char.spouse_id is None and age <= 40 and is_tracked_lineage(state, char):
            if rng.random() < MARRIAGE_CHANCE:
                spouse = create_spouse(state, char)
                if char.id in near:
                    origin = f" of the {spouse.origin}" if spouse.origin else ""
                    notes.append(f"{char.full_name} took {spouse.full_name}{origin} as a mate.")
        if char.gender == "female" and char.spouse_id and FERTILE_AGES[0] <= age <= FERTILE_AGES[1]:
            husband = state.character(char.spouse_id)
            if not husband or not husband.alive or len(char.children) >= MAX_CHILDREN:
                continue
            if not (is_tracked_lineage(state, char) or is_tracked_lineage(state, husband)):
                continue
            if rng.random() < BIRTH_CHANCE:
                child = create_character(
                    state,
                    child_role(state, husband, rng),
                    husband.settlement_id,
                    state.year,
                    mother=char,
                    father=husband,
                )
                # children inherit a blend of their parents' inclinations
                for t in child.tendencies:
                    child.tendencies[t] = 0.5 * child.tendencies[t] + 0.25 * (
                        char.tendencies.get(t, 0) + husband.tendencies.get(t, 0)
                    )
                child.adjust_affinity(char.id, 0.3)
                child.adjust_affinity(husband.id, 0.3)
                if char.id in near or husband.id in near or char.is_player or husband.is_player:
                    notes.append(f"{char.full_name} gave birth to {child.name}.")
    return notes


# --- who leads --------------------------------------------------------------
#
# A people this young has no settled way of passing on leadership: whoever the people
# look to most leads them, and they can turn to someone else while the leader lives.
# Only a custom of lineage, if they come to one, ties it to a family.

LEADER_AGE = 20
ELDER_STANDING = 8  # how much being an elder adds to someone's standing
STEP_ASIDE_AGE = 62
FRAIL_HEALTH = 30
STEP_ASIDE_CHANCE = 0.3  # a year in which a frail or old leader gives way
TURN_MARGIN = 1.3  # how far someone must outshine the leader before the people turn
TURN_LEAD = 10
TURN_CHANCE = 0.2
CANDIDATES = 4  # the most respected, among whom the people choose


def _adults(state, min_age=ADULT_AGE):
    return [c for c in state.living() if c.age(state.year) >= min_age]


def _strength(char):
    t = char.tendencies
    standing = 0.4 if char.is_elder else 0.0
    return char.health / 100 + t.get("ambitious", 0) + t.get("harsh", 0) + standing


def standing(char):
    """How much the people look to someone."""
    return char.means.get("regard") + (ELDER_STANDING if char.is_elder else 0)


# --- asking the people to follow --------------------------------------------------

FOLLOWER_WEIGHT = 0.25  # how much those who would follow someone add to their standing
BID_LOST_REGARD = 0.8  # what is left of one's standing after the people did not follow


def leader_failing(state):
    leader = state.leader
    return leader is None or (
        leader.age(state.year) >= STEP_ASIDE_AGE or leader.health < FRAIL_HEALTH
    )


def support(state, char, against):
    """The standing of the grown people who would follow `char` rather than `against`."""
    total = 0.0
    for c in state.living():
        if c is char or c is against or c.age(state.year) < ADULT_AGE:
            continue
        if feels(state, c, char) > feels(state, c, against) + 0.1:
            total += standing(c)
    return total


def bid_chance(state, char):
    """How likely the people are to follow someone who asks them to: by how they stand
    beside the leader, counting those each could draw after them, and more if the leader
    is failing."""
    leader = state.leader
    mine = standing(char)
    theirs = standing(leader) if leader else 1.0
    if leader is not None:
        mine += FOLLOWER_WEIGHT * support(state, char, leader)
        theirs += FOLLOWER_WEIGHT * support(state, leader, char)
    ratio = mine / max(1.0, theirs)
    failing = 0.3 if leader_failing(state) else 0.0
    return min(0.85, 0.05 + 0.6 * max(0.0, ratio - 0.8) + failing)


def bid_to_lead(state, char, rng):
    """Someone asks the people to follow them. Returns whether they did; if not, the
    asker's standing suffers and the leader thinks less of them."""
    leader = state.leader
    if rng.random() < bid_chance(state, char):
        make_leader(state, char)
        return True
    char.means.set("regard", char.means.get("regard") * BID_LOST_REGARD)
    if leader:
        leader.adjust_affinity(char.id, -0.3)
    return False


def _heir(state, old):
    kids = [state.character(c) for c in old.children] if old else []
    kids = [k for k in kids if k and k.alive and k.age(state.year) >= ADULT_AGE]
    return min(kids, key=lambda k: k.birth_year) if kids else None


def next_leader(state, old, rng=None):
    """Who the people turn to when the leader is gone (or giving way), by their custom."""
    rule = state.nation.succession
    if rule == "lineage":
        heir = _heir(state, old)
        if heir:
            return heir
    if rule == "strongest":
        adults = [c for c in _adults(state, LEADER_AGE) if c is not old]
        if adults:
            return max(adults, key=_strength)
    min_age = ELDER_AGE if rule == "council" else LEADER_AGE
    candidates = [c for c in _adults(state, min_age) if c is not old] or [
        c for c in _adults(state) if c is not old
    ]
    if not candidates:
        return None
    # the people choose among those they look to most; the most respected usually,
    # but not always
    candidates = sorted(candidates, key=standing, reverse=True)[:CANDIDATES]
    if rng is None:
        return candidates[0]
    top = standing(candidates[0])
    weights = [math.exp((standing(c) - top) / 8) for c in candidates]
    return rng.choices(candidates, weights)[0]


def make_leader(state, new):
    old = state.leader
    if old and old.alive and old is not new:
        old.station = old.former_station or "keeper"
        old.former_station = ""
    if new.station != "leader":
        new.former_station = new.station
    new.station = "leader"
    new.is_elder = False
    new.settlement_id = state.seat.id
    state.nation.leader_id = new.id
    state.nation.leading_family = new.family_name


def _turned_to(new):
    if new.is_player:
        return "[b]The people have turned to you to lead them.[/b]"
    return f"The people now look to {new.full_name} to lead them."


def succeed(state):
    """Find a new leader if the people have none. Returns a log line or ''."""
    leader = state.leader
    if leader and leader.alive:
        return ""
    new = next_leader(state, leader, state.rng())
    if new is None:
        new = create_character(state, "keeper", state.seat.id, state.year - 35)
    make_leader(state, new)
    return _turned_to(new)


def leadership_year(state):
    """While a leader lives, they may give way: grown old or frail, or outshone by
    someone the people now look to more. Returns a log line or ''."""
    leader = state.leader
    if leader is None or not leader.alive:
        return ""
    rng = state.rng()
    nation = state.nation
    frail = leader.age(state.year) >= STEP_ASIDE_AGE or leader.health < FRAIL_HEALTH
    if frail and rng.random() < STEP_ASIDE_CHANCE:
        new = next_leader(state, leader, rng)
        if new is None:
            return ""
        make_leader(state, new)
        leader.is_elder = True
        who = "You have" if leader.is_player else f"{leader.full_name} has"
        return f"{who} grown too old to lead and given way. " + _turned_to(new)
    if nation.succession == "lineage":
        return ""
    rival = next_leader(state, leader)
    if rival is None or rival.age(state.year) < LEADER_AGE:
        return ""
    if standing(rival) > TURN_MARGIN * standing(leader) + TURN_LEAD and rng.random() < TURN_CHANCE:
        make_leader(state, rival)
        who = "you" if leader.is_player else leader.full_name
        return f"The people no longer look to {who} as they did. " + _turned_to(rival)
    return ""


def ensure_elders(state):
    """Keep a few respected elders and, around the player, a few neighbours."""
    rng = state.rng()
    elders = [c for c in state.living() if c.is_elder]
    while len(elders) < ELDER_COUNT:
        candidate = next(
            (
                c
                for c in state.living()
                if not c.is_elder
                and not c.is_player
                and c.id != state.nation.leader_id
                and c.age(state.year) >= ELDER_AGE
                and c.settlement_id == state.seat.id
            ),
            None,
        )
        if candidate is None:
            role = rng.choice(["keeper", "keeper", "hunter", "gatherer", "maker"])
            candidate = create_character(
                state, role, state.seat.id, state.year - rng.randint(32, 55)
            )
            candidate.means.add({"regard": 10})
        candidate.is_elder = True
        elders.append(candidate)

    player = state.player
    neighbours = [
        c
        for c in state.living()
        if c.settlement_id == player.settlement_id
        and not c.is_player
        and c.id not in (player.spouse_id, player.mother_id, player.father_id)
        and c.id not in player.children
        and c.age(state.year) >= ADULT_AGE
    ]
    while len(neighbours) < NEIGHBOUR_COUNT:
        weights = {k: v for k, v in rebirth_weights(state.nation).items() if k != "leader"}
        role = rng.choices(list(weights), list(weights.values()))[0]
        neighbours.append(
            create_character(state, role, player.settlement_id, state.year - rng.randint(18, 55))
        )
