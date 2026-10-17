from constants.config import CULTURE_GROUPS

def format_tile_info(tile):
    if not tile:
        return "No tile selected."
    lines = [
        f"Tile ID: {tile.get('id')}\n"
        f"Coordinates: ({tile.get('q')}, {tile.get('r')})",
        f"Biome: {tile.get('biome', 'Unknown')} ({tile.get('abbr', '')})",
        f"Elevation: {tile.get('elevation', 0):.2f}",
        f"Moisture: {tile.get('moisture', 0):.2f}",
        "Resources:"
    ]
    resources = tile.get('resources', {})
    for res, val in resources.items():
        lines.append(f"  {res}: {val:.2f}")
    return "\n".join(lines)


def format_player_info(player):
    if not player.player:
        return "Player: Not started"
    s = player.player.state
    return (f"Player: {player.player.name}\n"
            f"Species: {s.species}  Age: {s.age}\n"
            f"Health: {s.health}    Karma: {player.player.karma}\n"
            f"Family: {player.player.family.name} Location: {player.player.family.home.get('id')}\n"
            f"Sociolinguistic Group: {CULTURE_GROUPS[player.player.family.home.get('biome').split(' ')[0]]['language_family']}\n"
            f"Father: {player.player.family.father}\n "
            f"Mother: {player.player.family.mother}\n"
            f"Lineage Type: {player.player.family.lineage_type}\n\n\n"
            )
