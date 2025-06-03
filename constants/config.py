# Elevation noise controls terrain height variation
ELEVATION_NOISE = {
    "scale": 100.0,       # Typical range: 50–150; higher = broader features
    "octaves": 5,         # Typical range: 4–6; more octaves = more detail
    "persistence": 0.4,   # Typical range: 0.3–0.5; controls amplitude drop-off
    "lacunarity": 2.0     # Typical range: ~2.0; controls frequency increase
}

# Moisture noise controls humidity variation across the map
MOISTURE_NOISE = {
    "scale": 50.0,        # Typical range: 25–75; smaller = more localized variation
    "octaves": 4,         # Typical range: 3–5
    "persistence": 0.4,   # Often same as elevation
    "lacunarity": 2.0
}

# Elevation thresholds for biome classification
# These values represent upper bounds for elevation categories.
# Elevation values range from 0.0 (lowest) to 1.0 (highest).

ELEVATION_THRESHOLDS = {
    "water": 0.3,      # Below this is ocean or large lake
    "lowland": 0.5,    # Wetlands, plains, coast
    "midland": 0.7,    # Forests, tundra
    "highland": 0.9,   # Mountains
    "peak": 1.0        # Upper bound
}

# Moisture thresholds for biome classification
# These values represent upper bounds for moisture categories.
# Moisture values range from 0.0 (driest) to 1.0 (wettest).

MOISTURE_THRESHOLDS = {
    "arid": 0.2,       # Desert
    "semi_arid": 0.4,  # Dry plains
    "temperate": 0.6,  # Forests, tundra
    "humid": 0.8,      # Wetlands, coasts
    "saturated": 1.0   # Swamps
}

# Resource types
RESOURCE_TYPES = [
    "water",
    "plant_food",
    "animal_food",
    "shelter_materials",
    "tool_materials",
    "fire_sources"
]

# Baseline resource quantities per biome (values can be adjusted later)
# Each resource is a float between 0.0 and 1.0 representing abundance
BIOME_RESOURCE_BASELINES = {
    "Forest": {
        "water": 0.6,
        "plant_food": 0.7,
        "animal_food": 0.6,
        "shelter_materials": 0.8,
        "tool_materials": 0.7,
        "fire_sources": 0.6
    },
    "Plains": {
        "water": 0.4,
        "plant_food": 0.6,
        "animal_food": 0.7,
        "shelter_materials": 0.4,
        "tool_materials": 0.5,
        "fire_sources": 0.4
    },
    "Mountains": {
        "water": 0.5,
        "plant_food": 0.2,
        "animal_food": 0.4,
        "shelter_materials": 0.6,
        "tool_materials": 0.8,
        "fire_sources": 0.3
    },
    "Desert": {
        "water": 0.1,
        "plant_food": 0.1,
        "animal_food": 0.2,
        "shelter_materials": 0.2,
        "tool_materials": 0.3,
        "fire_sources": 0.2
    },
    "Swamp": {
        "water": 0.9,
        "plant_food": 0.6,
        "animal_food": 0.5,
        "shelter_materials": 0.5,
        "tool_materials": 0.4,
        "fire_sources": 0.3
    },
    "Coast": {
        "water": 0.8,
        "plant_food": 0.4,
        "animal_food": 0.6,
        "shelter_materials": 0.5,
        "tool_materials": 0.5,
        "fire_sources": 0.4
    },
    "Tundra": {
        "water": 0.4,
        "plant_food": 0.2,
        "animal_food": 0.4,
        "shelter_materials": 0.3,
        "tool_materials": 0.6,
        "fire_sources": 0.3
    }
}

# Resource quantity variation range: +/- percentage to introduce randomness
RESOURCE_VARIATION_PERCENTAGE = 0.15  # 15%

# Hex tile geometry constants

# Length of one edge of the hex tile (radius)
HEX_EDGE_LENGTH = 10  # example value, adjust as needed

# Derived dimensions for convenience
HEX_WIDTH = 2 * HEX_EDGE_LENGTH  # width of the hex tile
HEX_HEIGHT = (3 ** 0.5) * HEX_EDGE_LENGTH  # height of the hex tile (height of an equilateral triangle times 2)

# Spacing between hex tile centers (depends on orientation)
HEX_HORIZONTAL_SPACING = HEX_WIDTH * 0.75  # distance between centers horizontally for pointy-top hex
HEX_VERTICAL_SPACING = HEX_HEIGHT  # vertical distance between centers for pointy-top hex

# Hex orientation: 'pointy' or 'flat'
HEX_ORIENTATION = 'pointy'  # choose 'pointy' for pointy-top hexagons

