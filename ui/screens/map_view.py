from kivy.uix.screenmanager import Screen
from kivy.graphics import Color, Line, Rectangle
from kivy.uix.widget import Widget
from kivy.core.text import Label as CoreLabel
from constants.config import (
    HEX_WIDTH, HEX_HEIGHT, HEX_HORIZONTAL_SPACING, HEX_VERTICAL_SPACING, HEX_ORIENTATION,
    HEX_EDGE_LENGTH, MAP_WIDTH, MAP_HEIGHT
)
from core.game_engine import generate_map

class MapScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.map_data = generate_map()
        self.canvas_widget = Widget()
        self.add_widget(self.canvas_widget)
        self.draw_map()

    def draw_map(self):
        self.canvas_widget.canvas.clear()
        with self.canvas_widget.canvas:
            for q, col in enumerate(self.map_data):
                for r, tile in enumerate(col):
                    x, y = self.get_tile_position(q, r)
                    self.draw_hex(x, y)
                    # Draw the abbreviation at the center of the hex
                    abbr = tile.get("abbr", "")
                    if abbr:
                        label = CoreLabel(text=abbr, font_size=12)
                        label.refresh()
                        texture = label.texture
                        Rectangle(
                            texture=texture,
                            pos=(x - texture.size[0] / 2, y - texture.size[1] / 2),
                            size=texture.size
                        )

    def draw_hex(self, x, y):
        Color(0, 1, 0) # RGB
        Line(points=self.hex_points(x, y), width=1)

    def get_tile_position(self, q, r):
        if HEX_ORIENTATION == 'pointy':
            x = q * HEX_HORIZONTAL_SPACING
            y = r * HEX_VERTICAL_SPACING + (q % 2) * (HEX_VERTICAL_SPACING / 2)
        else:
            x = q * HEX_WIDTH
            y = r * HEX_HEIGHT * 0.75
        return x, y

    def hex_points(self, x, y):
        from math import cos, sin, pi
        angle_offset = pi / 6 if HEX_ORIENTATION == 'pointy' else 0
        points = []
        for i in range(6):
            angle = 2 * pi * i / 6 + angle_offset
            points.append(x + HEX_EDGE_LENGTH * cos(angle))
            points.append(y + HEX_EDGE_LENGTH * sin(angle))
        return points + points[:2]

    def get_center_hex_pixel_pos(self):
        center_q = MAP_WIDTH // 2
        center_r = MAP_HEIGHT // 2
        return self.get_tile_position(center_q, center_r)
