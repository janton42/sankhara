from constants.config import RESOURCE_REGENERATION, RESOURCE_RENEWABLE, BIOME_RESOURCE_BASELINES

def regenerate_resources(game_map):
    """
    Regenerate resources for each tile in the map according to their regeneration rates and renewability.
    """
    for col in game_map:
        for tile in col:
            biome = tile.get("biome")
            max_resources = BIOME_RESOURCE_BASELINES.get(biome, {})
            for resource, value in tile["resources"].items():
                regen_rate = RESOURCE_REGENERATION.get(resource, 0)
                is_renewable = RESOURCE_RENEWABLE.get(resource, False)
                max_val = max_resources.get(resource, 1.0)
                if is_renewable and regen_rate > 0:
                    # Saturation-based regeneration: dR = rate * (max - current)
                    delta = regen_rate * (max_val - value)
                    tile["resources"][resource] = min(max_val, value + delta)
                # Non-renewables: no regeneration (could add fixed pool logic here if needed)
