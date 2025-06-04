import numpy as np
from noise import pnoise2
import random

from constants.config import (
    MAP_WIDTH,
    MAP_HEIGHT,
    ELEVATION_NOISE,
    MOISTURE_NOISE,
    ELEVATION_THRESHOLDS,
    MOISTURE_THRESHOLDS,
    RESOURCE_TYPES,
    BIOME_RESOURCE_BASELINES,
    RESOURCE_VARIATION_PERCENTAGE
)

def generate_perlin_noise(width, height, params):
    scale = params["scale"]
    octaves = params["octaves"]
    persistence = params["persistence"]
    lacunarity = params["lacunarity"]
    seed = params["seed"]

    return np.array([
        [pnoise2((x + seed) / scale, (y + seed) / scale,
                 octaves=octaves,
                 persistence=persistence,
                 lacunarity=lacunarity,
                 repeatx=1024,
                 repeaty=1024,
                 base=0)
         for y in range(height)]
        for x in range(width)
    ])

def normalize(array):
    min_val = np.min(array)
    max_val = np.max(array)
    if min_val == max_val:
        return np.zeros_like(array)
    return (array - min_val) / (max_val - min_val)

def assign_biome(elevation, moisture):
    landform = ''
    vegetation = ''
    for formation in ELEVATION_THRESHOLDS:
        elev_min, elev_max = ELEVATION_THRESHOLDS[formation]
        if elev_min <= elevation <= elev_max:
            landform = formation
            break
    for veg in MOISTURE_THRESHOLDS:
        moist_min, moist_max = MOISTURE_THRESHOLDS[veg]
        if moist_min <= moisture <= moist_max:
            vegetation = veg
            break
    if landform == '':
        landform = 'Not Hotdog'
    if vegetation == '':
        vegetation = 'Not Hotdog'
    biome = landform + ' ' + vegetation
    return biome

def assign_resources(biome):
    base = BIOME_RESOURCE_BASELINES.get(biome, {})
    resources = {}
    for res in RESOURCE_TYPES:
        val = base.get(res, 0)
        variation = val * RESOURCE_VARIATION_PERCENTAGE
        resources[res] = val + random.uniform(-variation, variation)
    return resources

def generate_map():
    elevation_noise = normalize(generate_perlin_noise(MAP_WIDTH, MAP_HEIGHT, ELEVATION_NOISE))
    moisture_noise = normalize(generate_perlin_noise(MAP_WIDTH, MAP_HEIGHT, MOISTURE_NOISE))

    game_map = []
    for q in range(MAP_WIDTH):
        col = []
        for r in range(MAP_HEIGHT):
            elev_val = elevation_noise[q][r]
            moist_val = moisture_noise[q][r]
            biome = assign_biome(elev_val, moist_val)
            resources = assign_resources(biome)
            tile = {
                "q": q,
                "r": r,
                "elevation": elev_val,
                "moisture": moist_val,
                "biome": biome,
                "resources": resources
            }
            col.append(tile)
        game_map.append(col)

    return game_map
