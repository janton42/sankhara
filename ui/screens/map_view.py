from kivy.uix.screenmanager import Screen
from kivy.graphics import Color, Line, Rectangle
from kivy.uix.widget import Widget
from kivy.core.text import Label as CoreLabel
from constants.config import (
    HEX_WIDTH, HEX_HEIGHT, HEX_HORIZONTAL_SPACING, HEX_VERTICAL_SPACING, HEX_ORIENTATION,
    HEX_EDGE_LENGTH, MAP_WIDTH, MAP_HEIGHT, BIOME_COLORS
)

class MapScreen(Screen):
    def __init__(self, on_tile_selected_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.map_data = None  # Will be set externally
        self.canvas_widget = Widget()
        self.add_widget(self.canvas_widget)
        self.canvas_widget.bind(on_touch_down=self.on_map_touch)
        self.on_tile_selected_callback = on_tile_selected_callback

    def draw_map(self):
        if self.map_data is None:
            return
        self.canvas_widget.canvas.clear()
        with self.canvas_widget.canvas:
            for q, col in enumerate(self.map_data):
                for r, tile in enumerate(col):
                    x, y = self.get_tile_position(q, r)
                    biome = tile.get("biome", "")
                    color = BIOME_COLORS.get(biome, (1, 1, 1, 1))
                    self.draw_hex(x, y, color)
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

    def draw_hex(self, x, y, color):
        Color(*color)
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

    def on_map_touch(self, widget, touch):
        # Convert touch coordinates to tile indices (q, r)
        q, r = self.pixel_to_hex(touch.x, touch.y)
        if 0 <= q < MAP_WIDTH and 0 <= r < MAP_HEIGHT:
            tile = self.map_data[q][r]
            self.on_tile_selected(tile)

    def pixel_to_hex(self, x, y):
        # Only works for pointy-top hexes
        # Approximate conversion from pixel to axial coordinates
        q = int(round(x / HEX_HORIZONTAL_SPACING))
        r = int(round((y - (q % 2) * (HEX_VERTICAL_SPACING / 2)) / HEX_VERTICAL_SPACING))
        return q, r

    def on_tile_selected(self, tile):
        # Call the callback if provided
        if self.on_tile_selected_callback:
            self.on_tile_selected_callback(tile)
        else:
            print(f"Tile selected: {tile}")
