"""Access to the generated map for a game. The map is rebuilt from the seed rather
than saved, so it is cached per seed."""

from functools import lru_cache

from sankhara.core.game_engine import generate_map
from sankhara.world.hexgrid import neighbors


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


def tile_fertility(t):
    r = t["resources"]
    return (r.get("plant_food", 0) + r.get("animal_food", 0) + r.get("fresh_water", 0)) / 3


def settlement_fertility(state, settlement):
    """Average fertility of the settlement's tile and its neighbours inside the realm."""
    territory = {tuple(t) for t in state.nation.territory}
    cells = [(settlement.col, settlement.row)] + [
        n for n in neighbors(settlement.col, settlement.row) if n in territory
    ]
    tiles = [tile(state, c, r) for c, r in cells]
    tiles = [t for t in tiles if t]
    return sum(tile_fertility(t) for t in tiles) / len(tiles)
