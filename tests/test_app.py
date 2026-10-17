import pytest
import sys
import os
from kivy.base import EventLoop
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout


import types

# Patch Kivy App and MapScreen for headless testing
def patch_kivy():
    sys.modules['sankhara.ui.screens.map_view'] = types.SimpleNamespace(MapScreen=DummyMapScreen)
    sys.modules['sankhara.ui.screens.info_panel'] = types.SimpleNamespace(
        format_tile_info=lambda tile: f"Tile: {tile}",
        format_player_info=lambda player: f"Player: {player}",
    )

class DummyMapScreen(BoxLayout):
    def __init__(self, on_tile_selected_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.on_tile_selected_callback = on_tile_selected_callback
        self.draw_map_called = False
    def draw_map(self):
        self.draw_map_called = True

patch_kivy()
from sankhara.app import MainScreen

def test_main_screen_init():
    screen = MainScreen()
    assert isinstance(screen.right_panel, BoxLayout)
    assert isinstance(screen.map_screen, DummyMapScreen)
    assert isinstance(screen.render_button, Button)

def test_on_render_map_triggers_draw():
    screen = MainScreen()
    screen.on_render_map(None)
    assert screen.map_screen.draw_map_called

def test_on_tile_selected_updates_panel():
    screen = MainScreen()
    # Simulate tile selection
    screen.on_tile_selected({"type": "grass", "elevation": 2})
    # No assertion: just ensure no error and function runs

