from sankhara.constants.config import (
    ACTIONS,
    BIOME_RESOURCE_BASELINES,
    RESOURCE_REGENERATION,
    RESOURCE_RENEWABLE,
)


def regenerate_resources(game_map):
    """
    Regenerate resources for each tile in the map according to their regeneration
    rates and renewability.
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
    actions_taken: list of action_id performed this turn (repeatable actions may appear
    more than once, and apply once per occurrence)

    Returns a list of effect dicts (name, count, health, karma, skipped) describing what
    was applied, before clamping.
    """
    effects = []
    for action in ACTIONS:
        action_id = action["id"]
        count = actions_taken.count(action_id)
        if count:
            # Apply positive effects for taken actions
            health = action.get("health", 0) * count
            karma = action.get("karma", 0) * count
            skipped = False
        elif action.get("skippable"):
            # Apply skip penalties for skippable actions not taken
            penalty = action.get("penalty_on_skip", {})
            health = penalty.get("health", 0)
            karma = penalty.get("karma", 0)
            skipped = True
        else:
            continue
        player.karma += karma
        player.state.health += health
        effects.append(
            {
                "name": action["name"],
                "count": count,
                "health": health,
                "karma": karma,
                "skipped": skipped,
            }
        )
    # Clamp karma and health
    player.karma = max(-1, min(1, player.karma))
    player.state.health = max(0, min(100, player.state.health))
    return effects
