
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
