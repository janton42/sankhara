# resource types, storage, consumption mechanics.


def calculate_extraction_efficiency(labor, tool_quality, tech_level, labor_half=10):
    """
    Calculates extraction efficiency with diminishing returns for labor.
    - labor: number of labor units applied
    - tool_quality: 0.0 (bare hands) to 2.0 (excellent tools)
    - tech_level: 0.0 (primitive) to 2.0 (advanced)
    - labor_half: labor at which 50% max efficiency is reached
    Returns a value between 0 and (tool_quality * tech_level)
    """
    # Michaelis-Menten (saturating) curve for labor
    labor_effect = labor / (labor + labor_half)
    # Tool and tech are linear multipliers (can be tuned)
    efficiency = labor_effect * tool_quality * tech_level
    return efficiency


def extract_resource(
    tile_resources, resource_type, labor, tool_quality, tech_level, max_extract_per_turn=1.0
):
    """
    Extracts resource from a tile's resource pool.
    - tile_resources: dict of resource pools for the tile
    - resource_type: string key
    - labor, tool_quality, tech_level: as above
    - max_extract_per_turn: max fraction of resource that can be extracted per turn
    Returns (amount_extracted, updated_tile_resources)
    """
    available = tile_resources.get(resource_type, 0)
    efficiency = calculate_extraction_efficiency(labor, tool_quality, tech_level)
    # Extraction is limited by available resource and max per turn
    extract_amount = min(available, max_extract_per_turn * efficiency)
    tile_resources[resource_type] = max(0, available - extract_amount)
    return extract_amount, tile_resources


def regenerate_resources(tile_resources, resource_regen, resource_renewable, resource_max):
    """
    Regenerates renewable resources up to their max, does not regenerate non-renewables.
    - tile_resources: dict of current resource pools
    - resource_regen: dict of regeneration rates (fraction per turn)
    - resource_renewable: dict of booleans
    - resource_max: dict of max values for each resource
    Returns updated tile_resources
    """
    for res, val in tile_resources.items():
        max_val = resource_max.get(res, 1.0)
        if resource_renewable.get(res, False):
            regen = resource_regen.get(res, 0)
            tile_resources[res] = min(max_val, val + regen * max_val)
        else:
            tile_resources[res] = max(0, val)  # Non-renewables do not regenerate
    return tile_resources
