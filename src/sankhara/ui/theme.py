"""Shared colours and small styled widgets for the Kivy UI."""

from kivy.graphics import Color, Rectangle
from kivy.uix.button import Button
from kivy.uix.label import Label

# Palette: dark warm background, saffron accent.
BACKGROUND = (0.10, 0.09, 0.08, 1)
PANEL = (0.15, 0.13, 0.12, 1)
BUTTON = (0.27, 0.23, 0.20, 1)
BUTTON_DOWN = (0.36, 0.30, 0.25, 1)
BUTTON_DISABLED = (0.18, 0.16, 0.14, 1)
ACCENT = (0.96, 0.62, 0.18, 1)
TEXT = (0.93, 0.90, 0.85, 1)
MUTED = (0.62, 0.58, 0.53, 1)
GOOD = (0.55, 0.80, 0.45, 1)
BAD = (0.90, 0.40, 0.35, 1)

ACCENT_HEX = "f59e2e"
MUTED_HEX = "9e9487"

# Map colours. Moisture picks the base hue; elevation shades it and, for high
# ground, blends it toward bare stone.
MOISTURE_COLORS = {
    "Saltflat": (0.86, 0.82, 0.72),
    "Desert": (0.85, 0.71, 0.45),
    "Steppe": (0.73, 0.68, 0.36),
    "Grassland": (0.52, 0.70, 0.33),
    "Shrubland": (0.45, 0.56, 0.30),
    "Forest": (0.20, 0.45, 0.22),
    "Wetland": (0.24, 0.54, 0.55),
}
STONE = (0.55, 0.53, 0.50)
# elevation band -> (brightness multiplier, blend toward stone)
ELEVATION_SHADING = {
    "Lowland": (0.78, 0.0),
    "Basin": (0.85, 0.0),
    "Valley": (0.92, 0.0),
    "Plain": (1.0, 0.0),
    "Hill": (0.95, 0.2),
    "Highland": (0.95, 0.4),
    "Mountain": (1.1, 0.65),
}


def biome_color(biome):
    """RGBA fill colour for a biome name like "Hill Forest"."""
    elevation, _, moisture = biome.partition(" ")
    base = MOISTURE_COLORS.get(moisture, (0.5, 0.5, 0.5))
    brightness, stone = ELEVATION_SHADING.get(elevation, (1.0, 0.0))
    rgb = [
        min(1.0, (c * (1 - stone) + s * stone) * brightness)
        for c, s in zip(base, STONE, strict=True)
    ]
    return (*rgb, 1)


def fill_background(widget, color):
    """Paint a solid background behind a widget that follows its size and position."""
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)

    def update(*_):
        rect.pos = widget.pos
        rect.size = widget.size

    widget.bind(pos=update, size=update)


class ThemedButton(Button):
    """Flat button in the game palette."""

    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_disabled_normal", "")
        kwargs.setdefault("color", TEXT)
        kwargs.setdefault("disabled_color", MUTED)
        super().__init__(**kwargs)
        self._refresh_background()
        self.bind(state=self._refresh_background, disabled=self._refresh_background)

    def _refresh_background(self, *_):
        if self.disabled:
            self.background_color = BUTTON_DISABLED
        elif self.state == "down":
            self.background_color = BUTTON_DOWN
        else:
            self.background_color = BUTTON


class AccentButton(ThemedButton):
    """Primary call-to-action button."""

    def _refresh_background(self, *_):
        if self.disabled:
            self.background_color = BUTTON_DISABLED
        elif self.state == "down":
            self.background_color = (0.80, 0.50, 0.14, 1)
        else:
            self.background_color = ACCENT
        self.color = TEXT if self.disabled else BACKGROUND


class WrapLabel(Label):
    """Left-aligned label whose text wraps to its width and whose height fits the text."""

    def __init__(self, **kwargs):
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "top")
        kwargs.setdefault("markup", True)
        kwargs.setdefault("color", TEXT)
        kwargs.setdefault("size_hint_y", None)
        super().__init__(**kwargs)
        self.bind(width=self._wrap, texture_size=self._fit_height)

    def _wrap(self, *_):
        self.text_size = (self.width, None)

    def _fit_height(self, *_):
        self.height = self.texture_size[1]


def heading(text):
    return f"[b][color={ACCENT_HEX}]{text}[/color][/b]"


def muted(text):
    return f"[color={MUTED_HEX}]{text}[/color]"
