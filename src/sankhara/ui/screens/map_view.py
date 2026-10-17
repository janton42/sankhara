from kivy.graphics import Color, Ellipse, Line, Mesh
from kivy.uix.widget import Widget

from sankhara.constants.config import MAP_HEIGHT, MAP_WIDTH
from sankhara.ui.theme import ACCENT, BACKGROUND, MUTED, OTHERS, TEXT, biome_color
from sankhara.world import hexgrid

MAP_PADDING = 8
OUTSIDE_DIM = 0.4  # brightness of land beyond the people's range
OTHERS_DIM = 0.6  # brightness of land other peoples range over


class MapScreen(Widget):
    """Draws the hex map scaled to fit the widget, row 0 at the top.

    Optionally shows the people's range: tiles outside it are dimmed, camps are
    marked, the player's home is outlined, and the ranges of other peoples the
    player knows of are shown in their own colour.
    """

    def __init__(self, on_tile_selected_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.map_data = None  # Will be set externally
        self.on_tile_selected_callback = on_tile_selected_callback
        self.selected_tile = None
        self.home_tile = None
        self.territory = None  # set of (col, row), or None to show everything
        self.settlements = []  # (col, row, population, is_seat)
        self.others = []  # (territory, (col, row) of their camp, population)
        self.other_tiles = set()
        self.hex_size = 0
        self.origin = (0, 0)  # top-left of the map's bounding box, in window coords
        self.bind(pos=self.draw_map, size=self.draw_map)

    def set_map(self, map_data):
        self.map_data = map_data
        self.selected_tile = None
        self.home_tile = None
        self.draw_map()

    def set_home(self, tile):
        self.home_tile = tile
        self.draw_map()

    def set_realm(self, territory, settlements, home=None, others=()):
        self.territory = {tuple(t) for t in territory}
        self.settlements = settlements
        self.others = list(others)
        self.other_tiles = {tuple(t) for terr, _, _ in self.others for t in terr}
        if home is not None and self.map_data:
            self.home_tile = self.map_data[home[0]][home[1]]
        self.draw_map()

    def _layout(self):
        """Fit the map inside the widget and centre it."""
        avail_w = max(0, self.width - 2 * MAP_PADDING)
        avail_h = max(0, self.height - 2 * MAP_PADDING)
        self.hex_size = hexgrid.fit_size(MAP_WIDTH, MAP_HEIGHT, avail_w, avail_h)
        map_w, map_h = hexgrid.map_pixel_size(MAP_WIDTH, MAP_HEIGHT, self.hex_size)
        self.origin = (self.center_x - map_w / 2, self.center_y + map_h / 2)

    def to_screen(self, x, y):
        """Map-space point (y down) to window coordinates (y up)."""
        return self.origin[0] + x, self.origin[1] - y

    def cell_center(self, col, row):
        return self.to_screen(*hexgrid.tile_center(col, row, self.hex_size))

    def tile_screen_center(self, tile):
        return self.cell_center(tile["q"], tile["r"])

    def draw_map(self, *_):
        self.canvas.clear()
        if self.map_data is None:
            return
        self._layout()
        size = self.hex_size
        with self.canvas:
            for col in self.map_data:
                for tile in col:
                    cx, cy = self.tile_screen_center(tile)
                    corners = hexgrid.hex_corners(cx, cy, size)
                    fill = biome_color(tile.get("biome", ""))
                    cell = (tile["q"], tile["r"])
                    if cell in self.other_tiles:
                        fill = _blend(fill, OTHERS, OTHERS_DIM)
                    elif self.territory is not None and cell not in self.territory:
                        fill = _blend(fill, BACKGROUND, OUTSIDE_DIM)
                    Color(*fill)
                    self._fill_hex(cx, cy, corners)
                    Color(fill[0] * 0.6, fill[1] * 0.6, fill[2] * 0.6, 1)
                    Line(points=corners, close=True, width=1)
            for terr, _, _ in self.others:
                self._draw_border(size, {tuple(t) for t in terr}, (*OTHERS[:3], 0.9))
            if self.territory:
                self._draw_border(size, self.territory, (*ACCENT[:3], 0.8))
            for _, (col, row), population in self.others:
                cx, cy = self.cell_center(col, row)
                dot = size * (0.22 + min(0.3, population / 8000))
                Color(*MUTED)
                Ellipse(pos=(cx - dot / 2, cy - dot / 2), size=(dot, dot))
            for col, row, population, is_seat in self.settlements:
                cx, cy = self.cell_center(col, row)
                dot = size * (0.22 + min(0.3, population / 8000))
                Color(*BACKGROUND)
                Ellipse(pos=(cx - dot / 2 - 2, cy - dot / 2 - 2), size=(dot + 4, dot + 4))
                Color(*(ACCENT if is_seat else TEXT))
                Ellipse(pos=(cx - dot / 2, cy - dot / 2), size=(dot, dot))
            if self.home_tile:
                cx, cy = self.tile_screen_center(self.home_tile)
                Color(*ACCENT)
                Line(points=hexgrid.hex_corners(cx, cy, size * 0.95), close=True, width=2)
            if self.selected_tile:
                cx, cy = self.tile_screen_center(self.selected_tile)
                Color(*TEXT)
                Line(points=hexgrid.hex_corners(cx, cy, size * 0.8), close=True, width=1.5)

    def _draw_border(self, size, territory, color):
        """Outline the edges of a range where one of its tiles meets the outside."""
        Color(*color)
        for col, row in territory:
            cx, cy = self.cell_center(col, row)
            corners = hexgrid.hex_corners(cx, cy, size)
            for ncol, nrow in hexgrid.neighbors(col, row):
                if (ncol, nrow) in territory:
                    continue
                ncx, ncy = self.cell_center(ncol, nrow)
                # the shared edge is the one whose midpoint lies toward the neighbour
                best = min(
                    range(6),
                    key=lambda k: (
                        ((corners[2 * k] + corners[(2 * k + 2) % 12]) / 2 - (cx + ncx) / 2) ** 2
                        + ((corners[2 * k + 1] + corners[(2 * k + 3) % 12]) / 2 - (cy + ncy) / 2)
                        ** 2
                    ),
                )
                a = 2 * best
                b = (2 * best + 2) % 12
                Line(points=[corners[a], corners[a + 1], corners[b], corners[b + 1]], width=1.6)

    @staticmethod
    def _fill_hex(cx, cy, corners):
        vertices = [cx, cy, 0, 0]
        for i in range(0, 12, 2):
            vertices += [corners[i], corners[i + 1], 0, 0]
        vertices += [corners[0], corners[1], 0, 0]
        Mesh(vertices=vertices, indices=list(range(8)), mode="triangle_fan")

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or self.map_data is None:
            return super().on_touch_down(touch)
        cell = hexgrid.pixel_to_tile(
            touch.x - self.origin[0],
            self.origin[1] - touch.y,
            self.hex_size,
            MAP_WIDTH,
            MAP_HEIGHT,
        )
        if cell is None:
            return super().on_touch_down(touch)
        col, row = cell
        self.on_tile_selected(self.map_data[col][row])
        return True

    def on_tile_selected(self, tile):
        self.selected_tile = tile
        self.draw_map()
        if self.on_tile_selected_callback:
            self.on_tile_selected_callback(tile)


def _blend(color, toward, keep):
    """Mix a colour toward another, keeping `keep` of the original."""
    return tuple(c * keep + b * (1 - keep) for c, b in zip(color[:3], toward[:3], strict=True)) + (
        1,
    )
