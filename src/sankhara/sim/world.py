"""Access to the generated map for a game. The map is rebuilt from the seed rather
than saved, so it is cached per seed."""

import math
from functools import lru_cache

from sankhara.core.game_engine import generate_map
from sankhara.entities.namer import make_family_name
from sankhara.world.hexgrid import distance, neighbors, tile_center

DIRECTIONS = (
    "east",
    "north-east",
    "north",
    "north-west",
    "west",
    "south-west",
    "south",
    "south-east",
)

GRASSY = ("Grassland", "Steppe", "Shrubland")


@lru_cache(maxsize=4)
def _map(seed):
    return generate_map(seed)


def map_for_seed(seed):
    return _map(seed)


def game_map(state):
    return _map(state.seed)


def tile(state, col, row):
    m = game_map(state)
    if 0 <= col < len(m) and 0 <= row < len(m[0]):
        return m[col][row]
    return None


def all_tiles(m):
    return [t for col in m for t in col]


def resource(t, name):
    return t["resources"].get(name, 0.0)


def tile_fertility(t):
    return (resource(t, "plant_food") + resource(t, "animal_food") + resource(t, "fresh_water")) / 3


def is_watery(t):
    return resource(t, "fresh_water") >= 0.75 or t["biome"].endswith("Wetland")


def is_grassy(t):
    return t["biome"].split(" ")[-1] in GRASSY and resource(t, "plant_food") >= 0.4


def forage_value(t, fishing=False):
    """How many people a tile can feed by foraging, hunting and (once known) fishing."""
    value = 0.5 * resource(t, "plant_food") + 0.4 * resource(t, "animal_food")
    value += 0.1 * resource(t, "fresh_water")
    if fishing and is_watery(t):
        value += 0.35
    return value


def territory_tiles(state):
    return [tile(state, c, r) for c, r in state.nation.territory]


def range_has(state, test):
    return any(test(t) for t in territory_tiles(state) if t)


def camp_tiles(state, settlement):
    """The land a camp lives off: its tile and the neighbours inside the people's range
    that are not closer to another camp."""
    territory = {tuple(t) for t in state.nation.territory}
    here = (settlement.col, settlement.row)
    cells = [here] + [n for n in neighbors(*here) if n in territory]
    others = [(s.col, s.row) for s in state.settlements.values() if s.id != settlement.id]
    mine = []
    for cell in cells:
        if cell != here and any(distance(cell, o) < distance(cell, here) for o in others):
            continue
        t = tile(state, *cell)
        if t:
            mine.append(t)
    return mine


def place_name(state, culture, rng):
    """A name for a new camp or people that nobody on the map already has."""
    taken = {s.name for s in state.settlements.values()} | {
        n.name for n in state.neighbours.values()
    }
    taken.add(state.nation.name)
    name = make_family_name(culture, rng)
    for _ in range(30):
        if name not in taken:
            break
        name = make_family_name(culture, rng)
    return name


def direction(origin, target):
    """Which way `target` lies from `origin`, as a compass word."""
    ox, oy = tile_center(*origin, 1.0)
    tx, ty = tile_center(*target, 1.0)
    angle = math.degrees(math.atan2(oy - ty, tx - ox)) % 360  # map y runs down
    return DIRECTIONS[round(angle / 45) % 8]
