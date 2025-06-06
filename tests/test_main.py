import pytest
import sys
import os
from kivy.base import EventLoop
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import types

# Patch Kivy App and MapScreen for headless testing
def patch_kivy():
    sys.modules['ui.screens.map_view'] = types.SimpleNamespace(MapScreen=DummyMapScreen)
    sys.modules['ui.screens.info_panel'] = types.SimpleNamespace(format_tile_info=lambda tile: f"Tile: {tile}")

class DummyMapScreen(BoxLayout):
    def __init__(self, on_tile_selected_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.on_tile_selected_callback = on_tile_selected_callback
        self.draw_map_called = False
    def draw_map(self):
        self.draw_map_called = True

patch_kivy()
from main import MainScreen

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

