from sankhara.entities.lineage import Family
from sankhara.entities.namer import make_name
from sankhara.entities.player import Player
from sankhara.entities.player_state import PlayerState
from sankhara.ui.screens.game_over import format_summary
from sankhara.ui.screens.info_panel import (
    format_effects,
    format_player_info,
    format_tile_info,
    resource_label,
)
from sankhara.ui.theme import biome_color

TILE = {
    "id": 9,
    "q": 2,
    "r": 3,
    "biome": "Hill Forest",
    "abbr": "HlFo",
    "elevation": 0.6512,
    "moisture": 0.8,
    "resources": {"fresh_water": 0.856, "plant_food": 1.0},
}


def make_player():
    family = Family("fam", TILE)
    family.set_family_name()
    player = Player("p1", family, PlayerState())
    player.karma = 0.1 + 0.2  # 0.30000000000000004
    player.set_player_gender()
    player.set_player_name()
    return player


def test_names_are_capitalised():
    first, last = make_name("Hill", "female").split(" ")
    assert first[0].isupper() and last[0].isupper()


def test_player_info_shows_name_and_family():
    player = make_player()
    text = format_player_info(player)
    assert player.name in text
    assert player.family.name in text
    assert format_player_info(None).startswith("Not yet born")


def test_tile_info_is_readable():
    text = format_tile_info(TILE)
    assert "Hill Forest" in text
    assert "Fresh water 0.86" in text
    assert "elevation 0.65" in text
    assert "home" not in text
    assert "home" in format_tile_info(TILE, home=TILE)


def test_resource_label():
    assert resource_label("tool_materials") == "Tool materials"


def test_effects_line():
    line = format_effects(
        3,
        [
            {"name": "Sleep", "count": 1, "health": 10, "karma": 0.1, "skipped": False},
            {"name": "Meditate", "count": 0, "health": 1, "karma": -0.1, "skipped": True},
        ],
    )
    assert line.startswith("[b]Day 3[/b]")
    assert "+10 hp" in line and "+0.10 karma" in line
    assert "skipped Meditate" in line and "−0.10 karma" in line
    assert "Nothing happened" in format_effects(1, [])


def test_summary_rounds_karma():
    summary = {
        "name": "Ana Bel",
        "family": "Bel",
        "home": "Hill Forest",
        "days": 4,
        "karma": 0.1 + 0.2,
        "cause": "health reached 0",
    }
    text = format_summary(summary)
    assert "+0.30" in text and "Lived 4 days" in text


def test_every_biome_has_a_distinct_colour():
    from sankhara.constants.config import ELEVATION_THRESHOLDS, MOISTURE_THRESHOLDS

    colours = {biome_color(f"{e} {m}") for e in ELEVATION_THRESHOLDS for m in MOISTURE_THRESHOLDS}
    assert len(colours) == len(ELEVATION_THRESHOLDS) * len(MOISTURE_THRESHOLDS)
