"""Other peoples on the map. They are simulated coarsely: they grow, come to know
things, drift toward or away from our people, share what they know, and
sometimes raid. Nobody commands armies; violence comes as events and choices.
"""

from sankhara.sim import discoveries
from sankhara.sim.state import Neighbour
from sankhara.sim.world import all_tiles, forage_value, game_map, place_name
from sankhara.world.hexgrid import distance, neighbors

NEIGHBOUR_COUNT = 3
MIN_DISTANCE = 5  # from our seat
LEARN_CHANCE = 0.03  # a neighbour coming to know something new, per year
SHARE_CHANCE = 0.05  # an idea passing between met peoples, per year at neutral relations
SHARE_AMOUNT = 0.3  # share of a discovery's cost an idea brings
CONTACT_CHANCE = 0.02
NEAR_CONTACT = 0.12  # extra chance a year when ranges come within reach of each other


def place_neighbours(state, culture_for, rng):
    """Scatter a few other peoples across the map, away from ours."""
    m = game_map(state)
    seat = (state.seat.col, state.seat.row)
    taken = {tuple(t) for t in state.nation.territory}
    sites = [
        t
        for t in all_tiles(m)
        if distance(seat, (t["q"], t["r"])) >= MIN_DISTANCE and forage_value(t) > 0.35
    ]
    rng.shuffle(sites)
    for t in sites:
        if len(state.neighbours) >= NEIGHBOUR_COUNT:
            break
        here = (t["q"], t["r"])
        if any(distance(here, (n.col, n.row)) < 4 for n in state.neighbours.values()):
            continue
        cells = [here] + [c for c in neighbors(*here) if _on_map(m, c) and c not in taken]
        culture = culture_for(t)
        n = Neighbour(
            id=state.new_id(),
            name=place_name(state, culture, rng),
            culture=culture,
            col=here[0],
            row=here[1],
            territory=[list(c) for c in cells],
            population=rng.uniform(180, 450),
            temper=rng.uniform(0.1, 0.9),
            known=list(discoveries.START_KNOWN),
        )
        state.neighbours[str(n.id)] = n
        taken.update(cells)


def _on_map(m, cell):
    return 0 <= cell[0] < len(m) and 0 <= cell[1] < len(m[0])


def _capacity(state, n):
    m = game_map(state)
    land = sum(forage_value(m[c][r]) for c, r in n.territory)
    mult = 1.8 if "cultivation" in n.known else 1.0
    return 40 * land * mult


def reach(state, n):
    """How close their range comes to ours."""
    ours = [tuple(t) for t in state.nation.territory]
    return min(distance(tuple(a), b) for a in n.territory for b in ours)


def relation_word(relations):
    if relations >= 0.5:
        return "close friends"
    if relations >= 0.15:
        return "friendly"
    if relations > -0.15:
        return "wary"
    if relations > -0.5:
        return "unfriendly"
    return "hostile"


def neighbours_year(state, rng):
    """Returns (log lines, things the player should be stopped for)."""
    notes, interrupts = [], []
    contact = discoveries.fx(state, "contact_mult")
    for n in state.neighbours.values():
        cap = _capacity(state, n)
        n.population += n.population * 0.02 * (1 - n.population / cap)
        n.population = max(40.0, n.population)

        # they learn too, from what they already know
        if rng.random() < LEARN_CHANCE:
            options = [
                d
                for d in discoveries.DISCOVERY_LIST
                if d.id not in n.known
                and d.cost
                and all(r in n.known for r in d.requires)
                and (not d.requires_any or any(r in n.known for r in d.requires_any))
            ]
            if options:
                n.known.append(rng.choice(options).id)

        if not n.met:
            chance = CONTACT_CHANCE + (NEAR_CONTACT if reach(state, n) <= 2 else 0)
            if rng.random() < chance * contact:
                n.met = True
                n.relations = rng.uniform(-0.2, 0.2) - 0.2 * (n.temper - 0.5)
                line = (
                    f"Strangers came to the edge of our lands: the {n.name}, who speak "
                    f"strangely but laugh at the same things."
                )
                notes.append(line)
                interrupts.append(f"Strangers: the {n.name}.")
            continue

        # relations drift toward what their temper and closeness make likely
        crowd = 0.08 if reach(state, n) <= 1 else 0
        drift_to = -0.4 * (n.temper - 0.4) - crowd
        n.relations += 0.05 * (drift_to - n.relations)
        n.relations = max(-1.0, min(1.0, n.relations))

        # ideas cross between peoples who talk
        if rng.random() < SHARE_CHANCE * (1 + n.relations):
            theirs = [
                d
                for d in discoveries.available(state)
                if d.id in n.known and d.id not in state.nation.known
            ]
            if theirs:
                d = rng.choice(theirs)
                discoveries.add_insight(state, d.id, d.cost * SHARE_AMOUNT)
                notes.append(f"From the {n.name}, our people picked up a new notion.")
            ours = [d for d in state.nation.known if d not in n.known]
            if ours and rng.random() < 0.5:
                n.known.append(rng.choice(ours))
    return notes, interrupts


def raid_chance(state, n):
    if not n.met or n.relations > -0.1:
        return 0.0
    return min(0.35, 0.2 * -n.relations * (0.5 + n.temper))
