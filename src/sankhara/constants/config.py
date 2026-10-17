# Elevation noise controls terrain height variation
ELEVATION_NOISE = {
    "scale": 80.0,  # Typical range: 50–150; higher = broader features
    "octaves": 4,  # Typical range: 4–6; more octaves = more detail
    "persistence": 0.3,  # Typical range: 0.3–0.5; controls amplitude drop-off
    "lacunarity": 2.0,  # Typical range: ~2.0; controls frequency increase
    "seed": 42,
}

MAP_WIDTH = 24
MAP_HEIGHT = 6

# Moisture noise controls humidity variation across the map
MOISTURE_NOISE = {
    "scale": 50.0,  # Typical range: 25–75; smaller = more localized variation
    "octaves": 4,  # Typical range: 3–5
    "persistence": 0.4,  # Often same as elevation
    "lacunarity": 2.0,
    "seed": 42,
}

# Elevation thresholds for biome classification
# These values represent upper bounds for elevation categories.
# Elevation values range from 0.0 (lowest) to 1.0 (highest).

ELEVATION_THRESHOLDS = {
    "Mountain": (0.90, 1.0),
    "Highland": (0.745, 0.90),
    "Hill": (0.60, 0.745),
    "Plain": (0.445, 0.60),
    "Valley": (0.30, 0.445),
    "Basin": (0.145, 0.30),
    "Lowland": (0.0, 0.145),
}

# Moisture thresholds for biome classification
# These values represent upper bounds for moisture categories.
# Moisture values range from 0.0 (driest) to 1.0 (wettest).

MOISTURE_THRESHOLDS = {
    "Saltflat": (0.0, 0.145),
    "Desert": (0.145, 0.30),
    "Steppe": (0.30, 0.445),
    "Grassland": (0.445, 0.60),
    "Shrubland": (0.60, 0.745),
    "Forest": (0.745, 0.90),
    "Wetland": (0.90, 1.0),
}

# Elevation and moisture abbreviations for biome naming
ELEVATION_ABBR = {
    "Mountain": "Mt",
    "Highland": "Hd",
    "Hill": "Hl",
    "Plain": "Pl",
    "Valley": "Vy",
    "Basin": "Bs",
    "Lowland": "Ll",
}

MOISTURE_ABBR = {
    "Wetland": "We",
    "Forest": "Fo",
    "Shrubland": "Sh",
    "Grassland": "Gr",
    "Steppe": "St",
    "Desert": "De",
    "Saltflat": "Sa",
}

# Resource types
RESOURCE_TYPES = [
    "fresh_water",
    "salt_water",
    "plant_food",
    "animal_food",
    "shelter_materials",
    "tool_materials",
    "fuel_sources",
]

# Resource regeneration rates per turn (as a fraction of max, for renewables)
RESOURCE_REGENERATION = {
    "fresh_water": 0.10,  # 10% of max per turn (example)
    "salt_water": 0.10,  # 10% of max per turn (example)
    "plant_food": 0.05,  # 5% of max per turn (example)
    "animal_food": 0.03,  # 3% of max per turn (example)
    "shelter_materials": 0.02,  # 2% of max per turn (example)
    "tool_materials": 0.0,  # Non-renewable (example)
    "fuel_sources": 0.01,  # 1% of max per turn (example)
}

# Resource renewability classification
RESOURCE_RENEWABLE = {
    "fresh_water": True,
    "salt_water": True,
    "plant_food": True,
    "animal_food": True,
    "shelter_materials": True,
    "tool_materials": False,
    "fuel_sources": False,  # Set to True if some are renewable (e.g., wood); adjust as needed
}

# Baseline resource quantities per biome (values can be adjusted later)
# Each resource is a float between 0.0 and 1.0 representing abundance
BIOME_RESOURCE_BASELINES = {
    "Mountain Wetland": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 0.8,
        "animal_food": 0.8,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 0.6,
    },
    "Mountain Forest": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 0.9,
        "animal_food": 0.9,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Mountain Shrubland": {
        "fresh_water": 0.8,
        "salt_water": 0.0,
        "plant_food": 0.6,
        "animal_food": 0.8,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 0.8,
    },
    "Mountain Grassland": {
        "fresh_water": 0.9,
        "salt_water": 0.0,
        "plant_food": 0.8,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 0.8,
    },
    "Mountain Steppe": {
        "fresh_water": 0.7,
        "salt_water": 0.0,
        "plant_food": 0.5,
        "animal_food": 0.7,
        "shelter_materials": 0.9,
        "tool_materials": 1.0,
        "fuel_sources": 0.7,
    },
    "Mountain Desert": {
        "fresh_water": 0.5,
        "salt_water": 0.0,
        "plant_food": 0.3,
        "animal_food": 0.5,
        "shelter_materials": 0.8,
        "tool_materials": 1.0,
        "fuel_sources": 0.5,
    },
    "Mountain Saltflat": {
        "fresh_water": 0.4,
        "salt_water": 1.0,
        "plant_food": 0.2,
        "animal_food": 0.4,
        "shelter_materials": 0.7,
        "tool_materials": 1.0,
        "fuel_sources": 0.4,
    },
    "Highland Wetland": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 0.9,
        "animal_food": 0.9,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 0.7,
    },
    "Highland Forest": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Highland Shrubland": {
        "fresh_water": 0.9,
        "salt_water": 0.0,
        "plant_food": 0.7,
        "animal_food": 0.9,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 0.9,
    },
    "Highland Grassland": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 0.9,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 0.9,
    },
    "Highland Steppe": {
        "fresh_water": 0.8,
        "salt_water": 0.0,
        "plant_food": 0.6,
        "animal_food": 0.8,
        "shelter_materials": 0.9,
        "tool_materials": 1.0,
        "fuel_sources": 0.8,
    },
    "Highland Desert": {
        "fresh_water": 0.6,
        "salt_water": 0.0,
        "plant_food": 0.4,
        "animal_food": 0.6,
        "shelter_materials": 0.8,
        "tool_materials": 1.0,
        "fuel_sources": 0.6,
    },
    "Highland Saltflat": {
        "fresh_water": 0.5,
        "salt_water": 1.0,
        "plant_food": 0.3,
        "animal_food": 0.5,
        "shelter_materials": 0.7,
        "tool_materials": 0.9,
        "fuel_sources": 0.5,
    },
    "Hill Wetland": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 0.8,
    },
    "Hill Forest": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Hill Shrubland": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 0.8,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Hill Grassland": {
        "fresh_water": 1.0,
        "salt_water": 0.0,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Hill Steppe": {
        "fresh_water": 0.9,
        "salt_water": 0.0,
        "plant_food": 0.7,
        "animal_food": 0.9,
        "shelter_materials": 0.9,
        "tool_materials": 1.0,
        "fuel_sources": 0.9,
    },
    "Hill Desert": {
        "fresh_water": 0.7,
        "salt_water": 0.0,
        "plant_food": 0.5,
        "animal_food": 0.7,
        "shelter_materials": 0.8,
        "tool_materials": 0.9,
        "fuel_sources": 0.7,
    },
    "Hill Saltflat": {
        "fresh_water": 0.6,
        "salt_water": 1.0,
        "plant_food": 0.4,
        "animal_food": 0.6,
        "shelter_materials": 0.7,
        "tool_materials": 0.8,
        "fuel_sources": 0.6,
    },
    "Plain Wetland": {
        "fresh_water": 1.0,
        "salt_water": 0.1,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 0.9,
        "fuel_sources": 0.8,
    },
    "Plain Forest": {
        "fresh_water": 1.0,
        "salt_water": 0.1,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Plain Shrubland": {
        "fresh_water": 0.9,
        "salt_water": 0.1,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Plain Grassland": {
        "fresh_water": 1.0,
        "salt_water": 0.1,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 0.9,
        "tool_materials": 0.9,
        "fuel_sources": 1.0,
    },
    "Plain Steppe": {
        "fresh_water": 0.8,
        "salt_water": 0.1,
        "plant_food": 0.9,
        "animal_food": 1.0,
        "shelter_materials": 0.8,
        "tool_materials": 0.9,
        "fuel_sources": 0.9,
    },
    "Plain Desert": {
        "fresh_water": 0.6,
        "salt_water": 0.1,
        "plant_food": 0.7,
        "animal_food": 0.8,
        "shelter_materials": 0.7,
        "tool_materials": 0.8,
        "fuel_sources": 0.7,
    },
    "Plain Saltflat": {
        "fresh_water": 0.5,
        "salt_water": 1.0,
        "plant_food": 0.6,
        "animal_food": 0.7,
        "shelter_materials": 0.6,
        "tool_materials": 0.7,
        "fuel_sources": 0.6,
    },
    "Valley Wetland": {
        "fresh_water": 1.0,
        "salt_water": 0.1,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 0.9,
        "tool_materials": 0.9,
        "fuel_sources": 0.8,
    },
    "Valley Forest": {
        "fresh_water": 1.0,
        "salt_water": 0.1,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Valley Shrubland": {
        "fresh_water": 1.0,
        "salt_water": 0.1,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 0.9,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Valley Grassland": {
        "fresh_water": 1.0,
        "salt_water": 0.1,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 0.8,
        "tool_materials": 0.9,
        "fuel_sources": 1.0,
    },
    "Valley Steppe": {
        "fresh_water": 1.0,
        "salt_water": 0.1,
        "plant_food": 0.9,
        "animal_food": 1.0,
        "shelter_materials": 0.7,
        "tool_materials": 0.9,
        "fuel_sources": 0.9,
    },
    "Valley Desert": {
        "fresh_water": 0.8,
        "salt_water": 0.1,
        "plant_food": 0.7,
        "animal_food": 0.8,
        "shelter_materials": 0.6,
        "tool_materials": 0.8,
        "fuel_sources": 0.7,
    },
    "Valley Saltflat": {
        "fresh_water": 0.7,
        "salt_water": 1.0,
        "plant_food": 0.6,
        "animal_food": 0.7,
        "shelter_materials": 0.5,
        "tool_materials": 0.7,
        "fuel_sources": 0.6,
    },
    "Basin Wetland": {
        "fresh_water": 1.0,
        "salt_water": 0.2,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 0.9,
        "tool_materials": 0.9,
        "fuel_sources": 0.7,
    },
    "Basin Forest": {
        "fresh_water": 1.0,
        "salt_water": 0.2,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Basin Shrubland": {
        "fresh_water": 1.0,
        "salt_water": 0.2,
        "plant_food": 0.9,
        "animal_food": 1.0,
        "shelter_materials": 0.9,
        "tool_materials": 1.0,
        "fuel_sources": 0.9,
    },
    "Basin Grassland": {
        "fresh_water": 1.0,
        "salt_water": 0.2,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 0.8,
        "tool_materials": 0.9,
        "fuel_sources": 0.9,
    },
    "Basin Steppe": {
        "fresh_water": 0.9,
        "salt_water": 0.2,
        "plant_food": 0.8,
        "animal_food": 0.9,
        "shelter_materials": 0.7,
        "tool_materials": 0.9,
        "fuel_sources": 0.8,
    },
    "Basin Desert": {
        "fresh_water": 0.7,
        "salt_water": 0.2,
        "plant_food": 0.6,
        "animal_food": 0.7,
        "shelter_materials": 0.6,
        "tool_materials": 0.8,
        "fuel_sources": 0.6,
    },
    "Basin Saltflat": {
        "fresh_water": 0.6,
        "salt_water": 1.0,
        "plant_food": 0.5,
        "animal_food": 0.6,
        "shelter_materials": 0.5,
        "tool_materials": 0.7,
        "fuel_sources": 0.5,
    },
    "Lowland Wetland": {
        "fresh_water": 1.0,
        "salt_water": 0.3,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 0.9,
        "tool_materials": 0.8,
        "fuel_sources": 0.7,
    },
    "Lowland Forest": {
        "fresh_water": 1.0,
        "salt_water": 0.3,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 1.0,
        "tool_materials": 1.0,
        "fuel_sources": 1.0,
    },
    "Lowland Shrubland": {
        "fresh_water": 1.0,
        "salt_water": 0.3,
        "plant_food": 0.9,
        "animal_food": 1.0,
        "shelter_materials": 0.9,
        "tool_materials": 0.9,
        "fuel_sources": 0.9,
    },
    "Lowland Grassland": {
        "fresh_water": 1.0,
        "salt_water": 0.3,
        "plant_food": 1.0,
        "animal_food": 1.0,
        "shelter_materials": 0.8,
        "tool_materials": 0.8,
        "fuel_sources": 0.9,
    },
    "Lowland Steppe": {
        "fresh_water": 1.0,
        "salt_water": 0.3,
        "plant_food": 0.8,
        "animal_food": 0.9,
        "shelter_materials": 0.7,
        "tool_materials": 0.8,
        "fuel_sources": 0.8,
    },
    "Lowland Desert": {
        "fresh_water": 0.9,
        "salt_water": 0.3,
        "plant_food": 0.6,
        "animal_food": 0.7,
        "shelter_materials": 0.6,
        "tool_materials": 0.7,
        "fuel_sources": 0.6,
    },
    "Lowland Saltflat": {
        "fresh_water": 0.8,
        "salt_water": 1.0,
        "plant_food": 0.5,
        "animal_food": 0.6,
        "shelter_materials": 0.5,
        "tool_materials": 0.6,
        "fuel_sources": 0.5,
    },
}

# Resource quantity variation range: +/- percentage to introduce randomness
RESOURCE_VARIATION_PERCENTAGE = 0.15  # 15%

# Biome color mapping for map display
BIOME_COLORS = {
    "Mountain Wetland": (0.5, 0.7, 1, 1),
    "Mountain Forest": (0.4, 0.6, 0.3, 1),
    "Mountain Shrubland": (0.7, 0.8, 0.5, 1),
    "Mountain Grassland": (0.7, 1, 0.6, 1),
    "Mountain Steppe": (0.9, 0.9, 0.5, 1),
    "Mountain Desert": (0.95, 0.85, 0.6, 1),
    "Mountain Saltflat": (1, 1, 0.9, 1),
    "Highland Wetland": (0.5, 0.8, 1, 1),
    "Highland Forest": (0.3, 0.7, 0.3, 1),
    "Highland Shrubland": (0.7, 0.9, 0.5, 1),
    "Highland Grassland": (0.7, 1, 0.7, 1),
    "Highland Steppe": (0.9, 0.95, 0.5, 1),
    "Highland Desert": (0.95, 0.9, 0.6, 1),
    "Highland Saltflat": (1, 1, 0.95, 1),
    "Hill Wetland": (0.5, 0.9, 1, 1),
    "Hill Forest": (0.2, 0.8, 0.2, 1),
    "Hill Shrubland": (0.8, 1, 0.6, 1),
    "Hill Grassland": (0.8, 1, 0.8, 1),
    "Hill Steppe": (0.95, 1, 0.5, 1),
    "Hill Desert": (1, 0.95, 0.7, 1),
    "Hill Saltflat": (1, 1, 1, 1),
    "Plain Wetland": (0.6, 1, 1, 1),
    "Plain Forest": (0.1, 0.9, 0.1, 1),
    "Plain Shrubland": (0.9, 1, 0.7, 1),
    "Plain Grassland": (0.9, 1, 0.9, 1),
    "Plain Steppe": (1, 1, 0.6, 1),
    "Plain Desert": (1, 1, 0.8, 1),
    "Plain Saltflat": (1, 1, 1, 1),
    "Valley Wetland": (0.7, 1, 1, 1),
    "Valley Forest": (0.2, 1, 0.2, 1),
    "Valley Shrubland": (1, 1, 0.8, 1),
    "Valley Grassland": (1, 1, 1, 1),
    "Valley Steppe": (1, 1, 0.7, 1),
    "Valley Desert": (1, 1, 0.9, 1),
    "Valley Saltflat": (1, 1, 1, 1),
    "Basin Wetland": (0.8, 1, 1, 1),
    "Basin Forest": (0.3, 1, 0.3, 1),
    "Basin Shrubland": (1, 1, 0.9, 1),
    "Basin Grassland": (1, 1, 1, 1),
    "Basin Steppe": (1, 1, 0.8, 1),
    "Basin Desert": (1, 1, 1, 1),
    "Basin Saltflat": (1, 1, 1, 1),
    "Lowland Wetland": (0.9, 1, 1, 1),
    "Lowland Forest": (0.4, 1, 0.4, 1),
    "Lowland Shrubland": (1, 1, 1, 1),
    "Lowland Grassland": (1, 1, 1, 1),
    "Lowland Steppe": (1, 1, 0.9, 1),
    "Lowland Desert": (1, 1, 1, 1),
    "Lowland Saltflat": (1, 1, 1, 1),
}

# Hex tile geometry constants

# Length of one edge of the hex tile (radius)
HEX_EDGE_LENGTH = 25  # example value, adjust as needed

# Derived dimensions for convenience
HEX_WIDTH = 2 * HEX_EDGE_LENGTH  # width of the hex tile
HEX_HEIGHT = (
    3**0.5
) * HEX_EDGE_LENGTH  # height of the hex tile (height of an equilateral triangle times 2)

# Spacing between hex tile centers (depends on orientation)
HEX_HORIZONTAL_SPACING = (
    HEX_WIDTH * 0.44
)  # distance between centers horizontally for pointy-top hex
HEX_VERTICAL_SPACING = HEX_HEIGHT * 1.79  # vertical distance between centers for pointy-top hex

# Hex orientation: 'pointy' or 'flat'
HEX_ORIENTATION = "pointy"  # choose 'pointy' for pointy-top hexagons

ACTIONS = [
    {
        "id": "sleep",
        "name": "Sleep",
        "hours": 6,
        "repeatable": False,
        "required": True,
        "skippable": True,
        "skip_limit": 3,  # Max times sleep can be skipped consecutively
        "penalty_on_skip": {"health": -10, "karma": -0.2},
        "karma": 0.1,
        "health": 10,  # Health gained if taken
        "description": "Rest and recover. Skipping reduces health.",
    },
    {
        "id": "eat_and_drink",
        "name": "Eat and Drink",
        "hours": 4,
        "repeatable": False,
        "required": True,
        "skippable": True,
        "skip_limit": 2,  # Max times eating/drinking can be skipped consecutively
        "penalty_on_skip": {"health": -8, "karma": -0.2},
        "karma": 0.1,
        "health": 8,  # Health gained if taken
        "description": "Consume food and water. Skipping reduces health.",
    },
    {
        "id": "gather_resources",
        "name": "Gather Resources",
        "hours": 4,
        "repeatable": True,
        "required": False,
        "skippable": False,
        "skip_limit": None,
        "penalty_on_skip": None,
        "karma": -0.05,
        "health": 0,
        "description": "Collect food, water, or materials.",
    },
    {
        "id": "meditate",
        "name": "Meditate",
        "hours": 4,
        "repeatable": True,
        "required": False,
        "skippable": True,
        "skip_limit": 5,  # Meditation can be skipped more often
        "penalty_on_skip": {"health": 1, "karma": -0.1},
        "karma": 0.2,
        "health": 2,
        "description": "Increase happiness and reduce stress.",
    },
]

CULTURE_GROUPS = {
    "Mountain": {
        "language_family": "Altaic",
        "male_stems": ["kar", "tan", "mor", "bel", "sar", "dur", "alt", "tem", "bol", "nur"],
        "female_stems": ["bel", "sar", "nur", "tem", "alt", "gul", "zol", "mel", "nay", "jin"],
        "male_suffixes": ["-ov", "-en", "-ar", "-ik", "-an", "-bek", "-tur", "-ash", "-jin"],
        "female_suffixes": ["-gul", "-ash", "-jin", "-nur", "-sen", "-bai", "-tem", "-yar", "-zel"],
        "last_stems": ["tog", "erk", "zan", "bul", "ket", "nur", "dal", "yurt", "tem"],
        "last_suffixes": ["-bay", "-dur", "-bek", "-gan", "-teg", "-sum", "-jin", "-tar", "-gul"],
    },
    "Highland": {
        "language_family": "Dravidian",
        "male_stems": ["thar", "mal", "var", "raj", "kan", "sel", "pon", "kum", "mur", "nall"],
        "female_stems": ["sel", "pon", "kum", "nall", "lal", "kam", "nila", "sri", "vana", "mala"],
        "male_suffixes": ["-an", "-ar", "-in", "-u", "-am", "-than", "-vel", "-kum", "-ram"],
        "female_suffixes": [
            "-i",
            "-a",
            "-am",
            "-ini",
            "-eswari",
            "-latha",
            "-vani",
            "-priya",
            "-shree",
        ],
        "last_stems": ["mani", "thiru", "arun", "kavi", "ravi", "sund", "pavi", "vel"],
        "last_suffixes": [
            "-nath",
            "-esan",
            "-kumar",
            "-vadi",
            "-selvan",
            "-rayan",
            "-appan",
            "-muthu",
        ],
    },
    "Hill": {
        "language_family": "Niger-Congo",
        "male_stems": [
            "bala",
            "kofi",
            "daka",
            "nko",
            "mba",
            "goma",
            "luba",
            "tunde",
            "tembo",
            "juma",
        ],
        "female_stems": [
            "zuba",
            "tala",
            "seka",
            "luba",
            "nala",
            "ama",
            "binta",
            "sade",
            "zola",
            "fola",
        ],
        "male_suffixes": ["-la", "-ko", "-ta", "-no", "-ba", "-ji", "-me", "-mu", "-do"],
        "female_suffixes": ["-lu", "-na", "-ji", "-ba", "-ka", "-sa", "-we", "-mi", "-yo"],
        "last_stems": ["kwame", "chidi", "zuba", "tembo", "bayo", "okon", "juma", "yaro"],
        "last_suffixes": ["-bwe", "-ngo", "-tunde", "-diko", "-lami", "-fari", "-soro", "-luba"],
    },
    "Plain": {
        "language_family": "Indo-European",
        "male_stems": ["al", "ber", "vin", "dom", "mar", "lor", "sten", "rol", "dra", "garr"],
        "female_stems": ["cel", "dra", "lor", "mar", "ela", "ina", "rosa", "tara", "nora", "lynn"],
        "male_suffixes": ["-son", "-man", "-berg", "-ski", "-strom", "-ich", "-gaard", "-hart"],
        "female_suffixes": ["-dottir", "-ley", "-lin", "-ette", "-ine", "-elle", "-a", "-ie"],
        "last_stems": ["stan", "garr", "thor", "eld", "wulf", "grim", "frey", "hald"],
        "last_suffixes": [
            "-stone",
            "-croft",
            "-ridge",
            "-ward",
            "-holm",
            "-hall",
            "-burn",
            "-well",
        ],
    },
    "Valley": {
        "language_family": "Afro-Asiatic",
        "male_stems": ["hab", "sal", "tan", "mur", "kah", "bar", "nas", "jab", "ram", "zid"],
        "female_stems": ["zam", "meh", "rim", "nas", "lay", "hana", "safa", "nura", "hiba", "mari"],
        "male_suffixes": ["-i", "-an", "-el", "-et", "-am", "-oun", "-ir", "-zem", "-al"],
        "female_suffixes": ["-a", "-ah", "-iya", "-een", "-et", "-un", "-is", "-in", "-ara"],
        "last_stems": ["zahir", "amin", "far", "jab", "sam", "naz", "rami", "kal"],
        "last_suffixes": ["-allah", "-bar", "-zad", "-oud", "-mir", "-sim", "-bari", "-qam"],
    },
    "Basin": {
        "language_family": "Austronesian",
        "male_stems": ["lan", "tal", "san", "bal", "kan", "toa", "riki", "tama", "matu", "nalu"],
        "female_stems": [
            "nur",
            "lim",
            "toa",
            "sina",
            "lani",
            "mele",
            "hana",
            "leia",
            "miri",
            "tiva",
        ],
        "male_suffixes": ["-an", "-un", "-in", "-ar", "-ki", "-mo", "-sa", "-o"],
        "female_suffixes": ["-el", "-lu", "-ti", "-na", "-ia", "-ra", "-me", "-ni", "-hi"],
        "last_stems": ["mana", "ratu", "lani", "tama", "koro", "sina", "tavi", "hoku"],
        "last_suffixes": ["-lani", "-hiva", "-kiri", "-tonga", "-riki", "-puna", "-nui", "-lua"],
    },
    "Lowland": {
        "language_family": "Sino-Tibetan",
        "male_stems": ["ming", "shan", "lei", "jun", "bo", "tian", "lin", "han", "gao", "xu"],
        "female_stems": ["hua", "zhen", "yue", "mei", "li", "lan", "xin", "feng", "xiu", "qi"],
        "male_suffixes": ["-li", "-wen", "-shan", "-kai", "-long", "-zhao", "-qin", "-hu"],
        "female_suffixes": ["-hua", "-jie", "-mei", "-xiu", "-lin", "-fang", "-na", "-yan"],
        "last_stems": ["zhang", "gao", "luo", "han", "cheng", "yang", "xu", "pei"],
        "last_suffixes": ["-fang", "-dong", "-quan", "-bo", "-xun", "-yi", "-zong", "-hai"],
    },
}
