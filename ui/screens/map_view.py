from kivy.uix.screenmanager import Screen
from kivy.graphics import Color, Line, Rectangle
from kivy.uix.widget import Widget
from constants.config import (
    HEX_WIDTH, HEX_HEIGHT, HEX_HORIZONTAL_SPACING, HEX_VERTICAL_SPACING, HEX_ORIENTATION
)
from world.map_gen import generate_map

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
            for col in self.map_data:
                for tile in col:
                    q, r = tile['q'], tile['r']
                    x, y = self.get_tile_position(q, r)
                    self.draw_hex(x, y)

    def draw_hex(self, x, y):
        Color(0, 1, 0) # RGB
        Line(points=self.hex_points(x, y), width=1)

    def get_tile_position(self, q, r):
        if HEX_ORIENTATION == 'pointy':
            x = HEX_WIDTH * (3/4 * q)
            y = HEX_HEIGHT * (r + q / 2)
        else:
            x = HEX_WIDTH * q
            y = HEX_HEIGHT * (3/4 * r)
        return x, y

    def hex_points(self, x, y):
        from math import cos, sin, pi
        angle_offset = pi / 6 if HEX_ORIENTATION == 'pointy' else 0
        points = []
        for i in range(6):
            points.append(x + HEX_WIDTH * cos(2 * pi * i / 6 + angle_offset))
            points.append(y + HEX_HEIGHT * sin(2 * pi * i / 6 + angle_offset))
        return points
