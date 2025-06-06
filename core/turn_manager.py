from constants.config import RESOURCE_REGENERATION, RESOURCE_RENEWABLE, BIOME_RESOURCE_BASELINES, ACTIONS

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

def process_player_actions(player, actions_taken):
    """
    Apply karma and health effects for all actions selected by the player at the end of the turn.
    actions_taken: list of action_id performed this turn
    """
    for action in ACTIONS:
        action_id = action["id"]
        if action_id in actions_taken:
            # Apply positive effects for taken actions
            player.karma += action.get("karma", 0)
            player.state.health += action.get("health", 0)
        elif action.get("skippable"):
            # Apply skip penalties for skippable actions not taken
            penalty = action.get("penalty_on_skip", {})
            player.karma += penalty.get("karma", 0)
            player.state.health += penalty.get("health", 0)
    # Clamp karma and health
    player.karma = max(-1, min(1, player.karma))
    player.state.health = max(0, min(100, player.state.health))
