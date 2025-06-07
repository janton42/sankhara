import random
from constants.config import ELEVATION_NOISE, MAP_HEIGHT, MAP_WIDTH, MOISTURE_NOISE
from world.map_gen import assign_biome, assign_resources, generate_perlin_noise, normalize, map_biome_abbr


def coin_flip():
    return 1 if random.random() < 0.5 else 0


def generate_map():
    elevation_noise = normalize(generate_perlin_noise(MAP_WIDTH, MAP_HEIGHT, ELEVATION_NOISE))
    moisture_noise = normalize(generate_perlin_noise(MAP_WIDTH, MAP_HEIGHT, MOISTURE_NOISE))

    game_map = []
    tile_id = 0
    for q in range(MAP_WIDTH):
        col = []
        for r in range(MAP_HEIGHT):
            elev_val = elevation_noise[q][r]
            moist_val = moisture_noise[q][r]
            biome = assign_biome(elev_val, moist_val)
            abbr = map_biome_abbr(biome)
            resources = assign_resources(biome)
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
