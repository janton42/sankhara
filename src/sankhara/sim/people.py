"""Tracked characters: creating them, families, ageing, death, marriage, births and who
leads the people.

Only people who matter are tracked individually: the leader and their family, the
respected elders, the player's family and a few neighbours. Everyone else is the
camps' population figures.
"""

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
    return state.add_character(char)


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
    for project in state.projects_of(char.id):
        if not char.is_player:
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


def _adults(state, min_age=ADULT_AGE):
    return [c for c in state.living() if c.age(state.year) >= min_age]


def _strength(char):
    t = char.tendencies
    standing = 0.4 if char.is_elder else 0.0
    return char.health / 100 + t.get("ambitious", 0) + t.get("harsh", 0) + standing


def next_leader(state, old):
    """Who the people turn to when the leader is gone, by their custom."""
    rule = state.nation.succession
    if rule == "lineage" and old:
        kids = [state.character(c) for c in old.children]
        kids = sorted(
            (k for k in kids if k and k.alive and k.age(state.year) >= ADULT_AGE),
            key=lambda k: k.birth_year,
        )
        if kids:
            return kids[0]
    if rule == "strongest":
        adults = _adults(state, 20)
        if adults:
            return max(adults, key=_strength)
    min_age = ELDER_AGE if rule == "council" else 20
    candidates = _adults(state, min_age) or _adults(state)
    if not candidates:
        return None

    # the most respected, and (by habit) a little toward the old leader's kin
    def standing(c):
        kin = 8 if old and old.id in (c.mother_id, c.father_id) else 0
        return c.means.get("regard") + kin + (20 if c.is_elder else 0)

    return max(candidates, key=standing)


def succeed(state):
    """Find a new leader if the people have none. Returns a log line or ''."""
    leader = state.leader
    if leader and leader.alive:
        return ""
    nation = state.nation
    new = next_leader(state, leader)
    if new is None:
        new = create_character(state, "leader", state.seat.id, state.year - 35)
    new.station = "leader"
    new.is_elder = False
    new.settlement_id = state.seat.id
    nation.leader_id = new.id
    nation.leading_family = new.family_name
    if new.is_player:
        return "[b]The people have turned to you to lead them.[/b]"
    return f"The people now look to {new.full_name} to lead them."


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
