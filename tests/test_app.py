from sankhara.app import MainScreen
from sankhara.constants.config import ACTIONS
from sankhara.ui.screens.map_view import MapScreen
from sankhara.ui.ui_kivy import InfoPanel


def test_main_screen_init():
    screen = MainScreen()
    assert isinstance(screen.left_panel, InfoPanel)
    assert isinstance(screen.map_screen, MapScreen)
    assert screen.map_screen.map_data is screen.game_map
    assert str(screen.seed) in screen.left_panel.seed_label.text


def test_each_game_gets_a_new_map():
    first, second = MainScreen(), MainScreen()
    assert first.seed != second.seed


def test_on_tile_selected_updates_panel():
    screen = MainScreen()
    tile = screen.game_map[3][4]
    screen.on_tile_selected(tile)
    assert tile["biome"] in screen.left_panel.tile_label.text


def test_starting_a_life_marks_home_on_map():
    screen = MainScreen()
    panel = screen.left_panel
    panel.on_start_game_wrapper(None)
    assert panel.player is not None
    assert screen.map_screen.home_tile is panel.player.family.home
    assert not any(btn.disabled for btn, _ in panel.action_dropdowns)


def test_ending_a_day_logs_and_resets_plan():
    screen = MainScreen()
    panel = screen.left_panel
    panel.on_start_game_wrapper(None)
    sleep = next(a for a in ACTIONS if a["id"] == "sleep")
    panel.select_action(0, sleep)
    assert "6 / 24" in panel.hours_label.text
    panel.on_take_action(None)
    assert panel.turn == 1
    assert panel.log_lines[0].startswith("[b]Day 1[/b]")
    assert panel.selected_actions == [None] * len(panel.selected_actions)


def test_death_summary():
    screen = MainScreen()
    panel = screen.left_panel
    panel.on_start_game_wrapper(None)
    panel.turn = 5
    summary = panel.death_summary()
    assert summary["days"] == 5
    assert summary["name"] == panel.player.name
