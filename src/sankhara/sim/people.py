"""Tracked characters: creating them, families, ageing, death, marriage, births and succession.

Only people who matter are tracked individually: the ruling house, advisors, the
player's family and a few neighbours. Everyone else is the settlements'
population figures.
"""

from sankhara.entities.namer import make_family_name, make_first_name
from sankhara.sim.state import Budget, Character
from sankhara.sim.stations import ADULT_AGE, STATIONS
from sankhara.sim.tendencies import random_tendencies

LIFESPAN_AFTER_ADULTHOOD = (20, 50)  # playable years of a life, before the hidden death
MARRIAGE_CHANCE = 0.25
BIRTH_CHANCE = 0.2
FERTILE_AGES = (18, 42)
MAX_CHILDREN = 5
ADVISOR_COUNT = 3
NEIGHBOUR_COUNT = 3


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
):
    rng = state.rng()
    culture = state.nation.culture
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
        household=Budget(**STATIONS[station].start),
        tendencies=tendencies if tendencies is not None else random_tendencies(rng, 0.4),
    )
    for parent in (mother, father):
        if parent:
            parent.children.append(char.id)
    return state.add_character(char)


def marry(a, b):
    a.spouse_id, b.spouse_id = b.id, a.id
    a.adjust_affinity(b.id, 0.3)
    b.adjust_affinity(a.id, 0.3)


def create_spouse(state, char):
    rng = state.rng()
    gender = "female" if char.gender == "male" else "male"
    age = max(ADULT_AGE, char.age(state.year) + rng.randint(-5, 5))
    spouse = create_character(
        state, char.station, char.settlement_id, state.year - age, gender=gender
    )
    spouse.family_name = char.family_name if char.gender == "male" else spouse.family_name
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
    """Whose marriages and children get tracked individually: the ruler and their
    children (the line of succession), and the player's immediate family."""
    player = state.player
    ruler_id = state.nation.ruler_id
    return (
        char.id == ruler_id
        or ruler_id in (char.mother_id, char.father_id)
        or char.id in (player.id, player.spouse_id, player.mother_id, player.father_id)
    )


def die(state, char, cause):
    char.alive = False
    char.death_year = state.year
    char.cause_of_death = cause
    spouse = state.character(char.spouse_id)
    if spouse and spouse.alive:
        spouse.spouse_id = None
        # a widowed spouse keeps a record of the marriage through the children
    if char.is_advisor:
        char.is_advisor = False


def age_and_health(state, char, rng):
    """Yearly drift in health. Returns a cause of death, or '' if they live on."""
    age = char.age(state.year)
    if age > 30:
        char.health -= 0.6 + max(0, age - 50) * 0.15
    char.health += rng.uniform(-2, 2.5)
    char.health = max(0.0, min(100.0, char.health))
    if age >= char.death_age:
        return (
            "old age"
            if age >= 55
            else rng.choice(["a sudden fever", "a fall", "a wasting illness"])
        )
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
    near.add(state.nation.ruler_id)

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
        # NPC marriages, only within lineages we track
        if char.spouse_id is None and age <= 40 and is_tracked_lineage(state, char):
            if rng.random() < MARRIAGE_CHANCE:
                spouse = create_spouse(state, char)
                if char.id in near or char.family_name == state.nation.dynasty:
                    notes.append(f"{char.full_name} married {spouse.full_name}.")
        # births
        if char.gender == "female" and char.spouse_id and FERTILE_AGES[0] <= age <= FERTILE_AGES[1]:
            husband = state.character(char.spouse_id)
            if not husband or not husband.alive or len(char.children) >= MAX_CHILDREN:
                continue
            if not (is_tracked_lineage(state, char) or is_tracked_lineage(state, husband)):
                continue
            if rng.random() < BIRTH_CHANCE:
                station = husband.station if husband.station != "ruler" else "noble"
                child = create_character(
                    state, station, husband.settlement_id, state.year, mother=char, father=husband
                )
                # children inherit a blend of their parents' inclinations
                for t in child.tendencies:
                    child.tendencies[t] = 0.5 * child.tendencies[t] + 0.25 * (
                        char.tendencies.get(t, 0) + husband.tendencies.get(t, 0)
                    )
                child.adjust_affinity(char.id, 0.3)
                child.adjust_affinity(husband.id, 0.3)
                if char.id in near or husband.id in near:
                    notes.append(f"{char.full_name} gave birth to {child.name}.")
    return notes


def line_of_succession(state, ruler):
    """Eldest living children first, then siblings."""
    kids = [state.character(c) for c in ruler.children]
    kids = sorted((k for k in kids if k and k.alive), key=lambda k: k.birth_year)
    sibs = sorted(siblings(state, ruler), key=lambda s: s.birth_year)
    return kids + sibs


def heir_of(state):
    ruler = state.ruler
    if not ruler:
        return None
    line = line_of_succession(state, ruler)
    return line[0] if line else None


def succeed(state):
    """Install a new ruler if the throne is empty. Returns a log line or ''."""
    ruler = state.ruler
    if ruler and ruler.alive:
        return ""
    nation = state.nation
    line = line_of_succession(state, ruler) if ruler else []
    if line:
        new = line[0]
        note = f"{new.full_name} succeeded to the throne."
    else:
        # the line has failed: the most senior advisor founds a new house
        advisors = [c for c in state.living() if c.is_advisor and c.age(state.year) >= ADULT_AGE]
        if advisors:
            new = max(advisors, key=lambda c: c.age(state.year))
            new.is_advisor = False
        else:
            capital = next(s for s in state.settlements.values() if s.is_capital)
            new = create_character(state, "noble", capital.id, state.year - 30)
        note = (
            f"The old line has ended. {new.full_name} took the throne, "
            f"founding House {new.family_name}."
        )
    # succession through a daughter passes the throne to her husband's house
    nation.dynasty = new.family_name
    new.station = "ruler"
    capital = next(s for s in state.settlements.values() if s.is_capital)
    new.settlement_id = capital.id
    nation.ruler_id = new.id
    return note


def ensure_court(state):
    """Keep the ruler supplied with advisors and the player with neighbours."""
    rng = state.rng()
    capital = next(s for s in state.settlements.values() if s.is_capital)
    advisors = [c for c in state.living() if c.is_advisor]
    while len(advisors) < ADVISOR_COUNT:
        candidate = next(
            (
                c
                for c in state.living()
                if c.station == "noble"
                and not c.is_advisor
                and not c.is_player
                and c.family_name != state.nation.dynasty
                and c.age(state.year) >= 25
            ),
            None,
        )
        if candidate is None:
            candidate = create_character(
                state, "noble", capital.id, state.year - rng.randint(28, 50)
            )
        candidate.is_advisor = True
        advisors.append(candidate)

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
        station = rng.choice(["farmer", "artisan", "merchant", "scholar"])
        neighbours.append(
            create_character(state, station, player.settlement_id, state.year - rng.randint(18, 60))
        )
