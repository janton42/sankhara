import random

from sankhara.constants.config import ELEVATION_NOISE, MAP_HEIGHT, MAP_WIDTH, MOISTURE_NOISE
from sankhara.world.map_gen import (
    assign_biome,
    assign_resources,
    generate_perlin_noise,
    map_biome_abbr,
    normalize,
)


def coin_flip():
    return 1 if random.random() < 0.5 else 0


def new_seed():
    return random.randrange(1_000_000)


def generate_map(seed=None):
    """Build a MAP_WIDTH x MAP_HEIGHT map; the same seed gives the same terrain."""
    if seed is None:
        seed = new_seed()
    elevation_noise = normalize(generate_perlin_noise(MAP_WIDTH, MAP_HEIGHT, ELEVATION_NOISE, seed))
    moisture_noise = normalize(
        generate_perlin_noise(MAP_WIDTH, MAP_HEIGHT, MOISTURE_NOISE, seed + 1)
    )
    rng = random.Random(seed)

    game_map = []
    tile_id = 0
    for q in range(MAP_WIDTH):
        col = []
        for r in range(MAP_HEIGHT):
            elev_val = elevation_noise[q][r]
            moist_val = moisture_noise[q][r]
            biome = assign_biome(elev_val, moist_val)
            abbr = map_biome_abbr(biome)
            resources = assign_resources(biome, rng)
            tile_id += 1
            tile = {
                "id": tile_id,
                "q": q,
                "r": r,
                "elevation": elev_val,
                "moisture": moist_val,
                "biome": biome,
                "abbr": abbr,
                "resources": resources,
            }
            col.append(tile)
        game_map.append(col)

    return game_map
