from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Mesh, Rectangle
from kivy.uix.stencilview import StencilView

from sankhara.constants.config import MAP_HEIGHT, MAP_WIDTH
from sankhara.ui.theme import ACCENT, BACKGROUND, BAD, GOOD, MUTED, OTHERS, TEXT, biome_color
from sankhara.world import hexgrid

MAP_PADDING = 8
OUTSIDE_DIM = 0.4  # brightness of land beyond the people's range
OTHERS_DIM = 0.6  # brightness of land other peoples range over
TRIBE_TINT = 0.85  # how much of the land's own colour shows under a tribe's tint
TRIBE_COLORS = (
    (0.95, 0.80, 0.55),
    (0.60, 0.80, 0.95),
    (0.85, 0.60, 0.85),
    (0.65, 0.90, 0.65),
    (0.95, 0.65, 0.55),
    (0.80, 0.80, 0.80),
)
MAX_ZOOM = 4.0
ZOOM_STEP = 1.25
NAMES_AT = 30  # hex size (pixels) from which camps are named rather than tribes
DRAG = 6  # pixels a touch may move and still count as a click
FOCUS_ZOOM = 2.5  # how close the map comes to a place chosen elsewhere


class MapScreen(StencilView):
    """Draws the hex map, row 0 at the top. Scrolling zooms in and out about the pointer
    and dragging moves the map, so the view runs from the whole people to one camp.

    Optionally shows the people's range: tiles outside it are dimmed, each tribe's land
    is tinted and outlined, camps are marked, the player's home is outlined, the camps
    where their ties live are joined to it by lines (warm solid, cold dashed), the camp of
    their last life is marked, and the ranges of other peoples the player knows of are
    shown in their own colour.
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
        self.tribes = []  # (name, [(col, row) of its camps])
        self.tribe_tiles = {}  # (col, row) -> index into self.tribes
        self.ties = []  # ((col, row), warmth -1..1, how many)
        self.ties_from = None  # (col, row) the ties are drawn from, if not home
        self.last_home = None  # (col, row)
        self.names = {}  # (col, row) -> camp name
        self.hex_size = 0
        self.zoom = 1.0
        self.pan = (0.0, 0.0)
        self.origin = (0, 0)  # top-left of the map's bounding box, in window coords
        self._texts = {}
        self.bind(pos=self.draw_map, size=self.draw_map)

    def set_map(self, map_data):
        self.map_data = map_data
        self.selected_tile = None
        self.home_tile = None
        self.zoom, self.pan = 1.0, (0.0, 0.0)
        self.draw_map()

    def set_home(self, tile):
        self.home_tile = tile
        self.draw_map()

    def set_realm(
        self,
        territory,
        settlements,
        home=None,
        others=(),
        tribes=(),
        ties=(),
        last_home=None,
        names=None,
        ties_from=None,
    ):
        self.territory = {tuple(t) for t in territory}
        self.settlements = settlements
        self.others = list(others)
        self.other_tiles = {tuple(t) for terr, _, _ in self.others for t in terr}
        self.tribes = list(tribes)
        self.tribe_tiles = _nearest_tribe(self.territory, self.tribes)
        self.ties = list(ties)
        self.ties_from = tuple(ties_from) if ties_from else None
        self.last_home = last_home
        self.names = dict(names or {})
        if home is not None and self.map_data:
            self.home_tile = self.map_data[home[0]][home[1]]
        self.draw_map()

    def show_ties(self, ties, origin=None):
        """Draw these ties instead, from `origin` (someone else's camp) or from home."""
        self.ties = list(ties)
        self.ties_from = tuple(origin) if origin else None
        self.draw_map()

    def focus(self, cell, zoom=FOCUS_ZOOM):
        """Come close to a place, centre it and select it."""
        self.zoom = max(self.zoom, zoom)
        self._layout()
        x, y = hexgrid.tile_center(*cell, self.hex_size)
        map_w, map_h = hexgrid.map_pixel_size(MAP_WIDTH, MAP_HEIGHT, self.hex_size)
        self.pan = (map_w / 2 - x, y - map_h / 2)
        self._clamp_pan()
        self.on_tile_selected(self.map_data[cell[0]][cell[1]])

    # --- where things are ---------------------------------------------------------

    def _fit(self):
        avail_w = max(0, self.width - 2 * MAP_PADDING)
        avail_h = max(0, self.height - 2 * MAP_PADDING)
        return hexgrid.fit_size(MAP_WIDTH, MAP_HEIGHT, avail_w, avail_h)

    def _layout(self):
        """Fit the map inside the widget, centre it, then apply zoom and pan."""
        self.hex_size = self._fit() * self.zoom
        map_w, map_h = hexgrid.map_pixel_size(MAP_WIDTH, MAP_HEIGHT, self.hex_size)
        self.origin = (
            self.center_x - map_w / 2 + self.pan[0],
            self.center_y + map_h / 2 + self.pan[1],
        )

    def to_screen(self, x, y):
        """Map-space point (y down) to window coordinates (y up)."""
        return self.origin[0] + x, self.origin[1] - y

    def cell_center(self, col, row):
        return self.to_screen(*hexgrid.tile_center(col, row, self.hex_size))

    def tile_screen_center(self, tile):
        return self.cell_center(tile["q"], tile["r"])

    def zoom_at(self, x, y, factor):
        """Zoom by `factor`, keeping the map point under (x, y) where it is."""
        self._layout()
        old = self.hex_size
        zoom = min(MAX_ZOOM, max(1.0, self.zoom * factor))
        if old <= 0 or zoom == self.zoom:
            return
        mx, my = (x - self.origin[0]) / old, (self.origin[1] - y) / old
        self.zoom = zoom
        self.pan = (0.0, 0.0)
        self._layout()
        new = self.hex_size
        self.pan = (x - mx * new - self.origin[0], y + my * new - self.origin[1])
        if self.zoom == 1.0:
            self.pan = (0.0, 0.0)
        self._clamp_pan()
        self.draw_map()

    def _clamp_pan(self):
        """Keep some of the map in view."""
        map_w, map_h = hexgrid.map_pixel_size(MAP_WIDTH, MAP_HEIGHT, self._fit() * self.zoom)
        limit_x = max(0.0, (map_w - self.width) / 2 + self.width / 3)
        limit_y = max(0.0, (map_h - self.height) / 2 + self.height / 3)
        self.pan = (
            min(limit_x, max(-limit_x, self.pan[0])),
            min(limit_y, max(-limit_y, self.pan[1])),
        )

    # --- drawing ------------------------------------------------------------------

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
                    elif cell in self.tribe_tiles and len(self.tribes) > 1:
                        tint = TRIBE_COLORS[self.tribe_tiles[cell] % len(TRIBE_COLORS)]
                        fill = _blend(fill, tint, TRIBE_TINT)
                    Color(*fill)
                    self._fill_hex(cx, cy, corners)
                    Color(fill[0] * 0.6, fill[1] * 0.6, fill[2] * 0.6, 1)
                    Line(points=corners, close=True, width=1)
            if len(self.tribes) > 1:
                for i in range(len(self.tribes)):
                    tiles = {c for c, t in self.tribe_tiles.items() if t == i}
                    self._draw_border(size, tiles, (*TEXT[:3], 0.45), width=1)
            for terr, _, _ in self.others:
                self._draw_border(size, {tuple(t) for t in terr}, (*OTHERS[:3], 0.9))
            if self.territory:
                self._draw_border(size, self.territory, (*ACCENT[:3], 0.8))
            self._draw_ties(size)
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
            if self.last_home:
                cx, cy = self.cell_center(*self.last_home)
                Color(*MUTED)
                Line(
                    points=hexgrid.hex_corners(cx, cy, size * 0.95),
                    close=True,
                    width=1,
                    dash_length=4,
                    dash_offset=3,
                )
            if self.home_tile:
                cx, cy = self.tile_screen_center(self.home_tile)
                Color(*ACCENT)
                Line(points=hexgrid.hex_corners(cx, cy, size * 0.95), close=True, width=2)
            if self.selected_tile:
                cx, cy = self.tile_screen_center(self.selected_tile)
                Color(*TEXT)
                Line(points=hexgrid.hex_corners(cx, cy, size * 0.8), close=True, width=1.5)
            self._draw_names(size)

    def _draw_ties(self, size):
        """Lines from home (or whoever was chosen) to where their ties live; ties at home ring
        it."""
        if self.ties_from:
            home = self.ties_from
        elif self.home_tile:
            home = (self.home_tile["q"], self.home_tile["r"])
        else:
            return
        hx, hy = self.cell_center(*home)
        for cell, warmth, count in self.ties:
            color = _blend(MUTED, GOOD if warmth >= 0 else BAD, 1 - min(1.0, abs(warmth) * 1.5))
            Color(*color[:3], 0.9)
            if tuple(cell) == home:
                Line(circle=(hx, hy, size * 0.62), width=1 + min(2.5, count * 0.4))
                continue
            cx, cy = self.cell_center(*cell)
            if warmth >= 0:
                Line(points=[hx, hy, cx, cy], width=1 + min(2.5, count * 0.4))
            else:
                Line(points=[hx, hy, cx, cy], width=1, dash_length=5, dash_offset=4)
            Line(circle=(cx, cy, size * 0.5), width=1.2)

    def _draw_names(self, size):
        """Tribes named over their camps when the whole people is in view; camps named
        once the view is close enough to tell them apart."""
        if size >= NAMES_AT:
            labels = [(name, [cell]) for cell, name in self.names.items()]
            offset = size * 0.7
        elif len(self.tribes) > 1:
            labels = self.tribes
            offset = 0
        else:
            return
        for name, cells in labels:
            points = [self.cell_center(*c) for c in cells]
            x = sum(p[0] for p in points) / len(points)
            y = sum(p[1] for p in points) / len(points) - offset
            texture = self._text(name)
            w, h = texture.size
            Color(*BACKGROUND[:3], 0.6)
            Rectangle(pos=(x - w / 2 - 3, y - h / 2 - 1), size=(w + 6, h + 2))
            Color(1, 1, 1, 1)
            Rectangle(texture=texture, pos=(x - w / 2, y - h / 2), size=texture.size)

    def _text(self, text):
        if text not in self._texts:
            label = CoreLabel(text=text, font_size=12, color=TEXT)
            label.refresh()
            self._texts[text] = label.texture
        return self._texts[text]

    def _draw_border(self, size, territory, color, width=1.6):
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
                Line(points=[corners[a], corners[a + 1], corners[b], corners[b + 1]], width=width)

    @staticmethod
    def _fill_hex(cx, cy, corners):
        vertices = [cx, cy, 0, 0]
        for i in range(0, 12, 2):
            vertices += [corners[i], corners[i + 1], 0, 0]
        vertices += [corners[0], corners[1], 0, 0]
        Mesh(vertices=vertices, indices=list(range(8)), mode="triangle_fan")

    # --- touch --------------------------------------------------------------------

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or self.map_data is None:
            return super().on_touch_down(touch)
        if touch.is_mouse_scrolling:
            if touch.button == "scrolldown":
                self.zoom_at(touch.x, touch.y, ZOOM_STEP)
            elif touch.button == "scrollup":
                self.zoom_at(touch.x, touch.y, 1 / ZOOM_STEP)
            return True
        touch.grab(self)
        touch.ud["map_start"] = (touch.x, touch.y, self.pan)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)
        x0, y0, pan = touch.ud["map_start"]
        if self.zoom > 1.0 and abs(touch.x - x0) + abs(touch.y - y0) > DRAG:
            self.pan = (pan[0] + touch.x - x0, pan[1] + touch.y - y0)
            self._clamp_pan()
            self.draw_map()
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        x0, y0, _ = touch.ud["map_start"]
        if abs(touch.x - x0) + abs(touch.y - y0) <= DRAG:
            self.select_at(touch.x, touch.y)
        return True

    def select_at(self, x, y):
        self._layout()
        cell = hexgrid.pixel_to_tile(
            x - self.origin[0], self.origin[1] - y, self.hex_size, MAP_WIDTH, MAP_HEIGHT
        )
        if cell is not None:
            col, row = cell
            self.on_tile_selected(self.map_data[col][row])

    def on_tile_selected(self, tile):
        self.selected_tile = tile
        self.draw_map()
        if self.on_tile_selected_callback:
            self.on_tile_selected_callback(tile)


def _nearest_tribe(territory, tribes):
    """Each tile of the range belongs to the tribe of its nearest camp."""
    camps = [(cell, i) for i, (_, cells) in enumerate(tribes) for cell in cells]
    if not camps:
        return {}
    return {
        tile: min(camps, key=lambda c: (hexgrid.distance(tile, c[0]), c[1]))[1]
        for tile in territory
    }


def _blend(color, toward, keep):
    """Mix a colour toward another, keeping `keep` of the original."""
    return tuple(c * keep + b * (1 - keep) for c, b in zip(color[:3], toward[:3], strict=True)) + (
        1,
    )
