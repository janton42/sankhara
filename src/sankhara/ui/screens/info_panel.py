from sankhara.constants.config import CULTURE_GROUPS, RESOURCE_TYPES
from sankhara.ui.theme import muted

GOOD_HEX = "8ccc73"
BAD_HEX = "e66659"


def resource_label(resource):
    """'fresh_water' -> 'Fresh water'."""
    return resource.replace("_", " ").capitalize()


def signed(value, decimals=0, suffix=""):
    """Coloured, signed number for effect summaries, e.g. '+10 hp' in green."""
    text = f"{value:+.{decimals}f}{suffix}".replace("-", "−")
    colour = GOOD_HEX if value > 0 else BAD_HEX
    return f"[color={colour}]{text}[/color]"


def format_tile_info(tile, home=None):
    if not tile:
        return "Click a tile on the map to inspect it."
    title = f"{tile.get('biome', 'Unknown')} ({tile.get('abbr', '')})"
    if home is not None and tile.get("id") == home.get("id"):
        title += "  • home"
    lines = [
        title,
        muted(
            f"Tile {tile.get('id')} at ({tile.get('q')}, {tile.get('r')})  ·  "
            f"elevation {tile.get('elevation', 0):.2f}  ·  moisture {tile.get('moisture', 0):.2f}"
        ),
    ]
    resources = tile.get("resources", {})
    cells = [f"{resource_label(r)} {resources[r]:.2f}" for r in RESOURCE_TYPES if r in resources]
    for i in range(0, len(cells), 2):
        lines.append("    ".join(cells[i : i + 2]))
    return "\n".join(lines)


def format_player_info(player):
    if not player:
        return "Not yet born. Press [b]Start Life[/b] to begin."
    s = player.state
    family = player.family
    culture = family.home.get("biome").split(" ")[0]
    return "\n".join(
        [
            f"[b]{player.name}[/b]  {muted(f'{s.species}, age {s.age}')}",
            f"Family {family.name} ({family.lineage_type})",
            f"Father {family.father}  ·  Mother {family.mother}",
            muted(
                f"{CULTURE_GROUPS[culture]['language_family']} speakers  ·  "
                f"home: {family.home.get('biome')}"
            ),
        ]
    )


def format_effects(day, effects):
    """One log line summarising a day's action effects."""
    parts = []
    for e in effects:
        name = e["name"] + (f" ×{e['count']}" if e["count"] > 1 else "")
        if e["skipped"]:
            name = muted(f"skipped {name}")
        deltas = []
        if e["health"]:
            deltas.append(signed(e["health"], suffix=" hp"))
        if e["karma"]:
            deltas.append(signed(e["karma"], 2, " karma"))
        parts.append(" ".join([name, *deltas]))
    body = ";  ".join(parts) if parts else "Nothing happened."
    return f"[b]Day {day}[/b]  {body}"
