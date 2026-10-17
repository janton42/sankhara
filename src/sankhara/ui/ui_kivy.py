import random

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.dropdown import DropDown
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from sankhara.core.day_plan import DAY_HOURS, available_actions, hours_used
from sankhara.core.turn_manager import process_player_actions, regenerate_resources
from sankhara.entities.lineage import Family
from sankhara.entities.player import Player
from sankhara.entities.player_state import PlayerState
from sankhara.ui.screens.info_panel import (
    format_effects,
    format_player_info,
    format_tile_info,
    signed,
)
from sankhara.ui.theme import (
    ACCENT,
    BAD,
    BUTTON_DISABLED,
    GOOD,
    MUTED,
    PANEL,
    TEXT,
    AccentButton,
    ThemedButton,
    WrapLabel,
    fill_background,
    heading,
    muted,
)

ACTION_SLOTS = 4
LOG_LENGTH = 30


def action_option_text(action):
    """Dropdown entry text, e.g. 'Sleep · 6h · +10 hp +0.10 karma'."""
    effects = []
    if action.get("health"):
        effects.append(signed(action["health"], suffix=" hp"))
    if action.get("karma"):
        effects.append(signed(action["karma"], 2, " karma"))
    return f"{action['name']} · {action['hours']}h · {' '.join(effects)}"


class Bar(Widget):
    """Flat horizontal bar. Fills from the left, or from the middle when `centered`
    (for values that can be negative, like karma)."""

    def __init__(self, minimum, maximum, centered=False, **kwargs):
        super().__init__(**kwargs)
        self.minimum, self.maximum, self.centered = minimum, maximum, centered
        self.value = minimum
        self.fill_color = ACCENT
        self.bind(pos=self.redraw, size=self.redraw)

    def set(self, value, color):
        self.value = max(self.minimum, min(self.maximum, value))
        self.fill_color = color
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        span = self.maximum - self.minimum
        bar_h = 8
        y = self.center_y - bar_h / 2
        with self.canvas:
            Color(*BUTTON_DISABLED)
            Rectangle(pos=(self.x, y), size=(self.width, bar_h))
            Color(*self.fill_color)
            if self.centered:
                mid = self.x + self.width / 2
                w = self.width / 2 * self.value / (span / 2)
                Rectangle(pos=(min(mid, mid + w), y), size=(abs(w), bar_h))
                Color(*MUTED)
                Rectangle(pos=(mid - 1, y - 3), size=(2, bar_h + 6))
            else:
                w = self.width * (self.value - self.minimum) / span
                Rectangle(pos=(self.x, y), size=(w, bar_h))


class StatBar(BoxLayout):
    """A labelled bar, e.g. 'Health 80' with a bar out of 100."""

    def __init__(self, name, minimum, maximum, centered=False, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=22, **kwargs)
        self.name = name
        self.label = Label(
            text="", size_hint_x=None, width=120, halign="left", color=TEXT, markup=True
        )
        self.label.bind(size=lambda lbl, size: setattr(lbl, "text_size", size))
        self.bar = Bar(minimum, maximum, centered)
        self.add_widget(self.label)
        self.add_widget(self.bar)

    def set(self, text, value, color):
        self.label.text = f"{self.name} {text}"
        self.bar.set(value, color)


class InfoPanel(BoxLayout):
    def __init__(self, on_life_started=None, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.spacing = 6
        self.padding = [14, 12, 14, 12]
        fill_background(self, PANEL)
        self.player = None
        self.game_map = None
        self.turn = 0
        self.selected_tile = None
        self.on_life_started = on_life_started
        self.selected_actions = [None] * ACTION_SLOTS

        # Header: day counter and map seed
        header = BoxLayout(size_hint_y=None, height=30)
        self.turn_label = Label(text=heading("Sankhara"), markup=True, halign="left", font_size=20)
        self.turn_label.bind(size=lambda lbl, size: setattr(lbl, "text_size", size))
        self.seed_label = Label(text="", color=MUTED, halign="right", size_hint_x=0.8)
        self.seed_label.bind(size=lambda lbl, size: setattr(lbl, "text_size", size))
        header.add_widget(self.turn_label)
        header.add_widget(self.seed_label)
        self.add_widget(header)

        # Player
        self.add_widget(WrapLabel(text=heading("Player")))
        self.player_label = WrapLabel(text=format_player_info(None))
        self.add_widget(self.player_label)
        self.health_bar = StatBar("Health", 0, 100)
        self.karma_bar = StatBar("Karma", -1, 1, centered=True)
        self.add_widget(self.health_bar)
        self.add_widget(self.karma_bar)

        # Today's plan
        self.hours_label = WrapLabel(text=heading("Today"))
        self.add_widget(self.hours_label)
        self.action_box = GridLayout(cols=2, size_hint_y=None, height=74, spacing=4)
        self.action_dropdowns = []
        for i in range(ACTION_SLOTS):
            dropdown = DropDown(auto_width=False, width=330)
            main_button = ThemedButton(text=f"Action {i + 1}", disabled=True)
            main_button.bind(on_release=lambda btn, i=i: self.open_dropdown(i, btn))
            self.action_box.add_widget(main_button)
            self.action_dropdowns.append((main_button, dropdown))
        self.add_widget(self.action_box)
        self.start_button = AccentButton(text="Start Life", size_hint_y=None, height=40, bold=True)
        self.start_button.bind(on_press=self.on_start_game_wrapper)
        self.add_widget(self.start_button)

        # Selected tile
        self.add_widget(WrapLabel(text=heading("Tile")))
        self.tile_label = WrapLabel(text=format_tile_info(None))
        self.add_widget(self.tile_label)

        # Log of past days, newest first
        self.add_widget(WrapLabel(text=heading("Log")))
        self.log_lines = []
        self.log_label = WrapLabel(text=muted("Nothing has happened yet."), font_size=13)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.log_label)
        self.add_widget(scroll)

        self.refresh_player()
        self.refresh_hours()

    # --- setup -----------------------------------------------------------

    def set_game_map(self, game_map, seed=None):
        self.game_map = game_map
        self.seed_label.text = f"seed {seed}" if seed is not None else ""

    def on_start_game_wrapper(self, instance):
        # Pick a random tile from the map
        if not self.game_map:
            return
        flat_tiles = [tile for col in self.game_map for tile in col]
        tile = random.choice(flat_tiles)
        self.on_start_game(instance, tile)

    def on_start_game(self, instance, tile):
        family = Family(family_id="fam1", start_tile=tile)
        family.set_family_name()
        state = PlayerState()
        self.player = Player(player_id="p1", family=family, state=state)
        self.player.set_player_gender()
        self.player.set_player_name()
        self.start_button.text = "End Day"
        self.start_button.unbind(on_press=self.on_start_game_wrapper)
        self.start_button.bind(on_press=self.on_take_action)
        self.reset_plan()
        self.refresh_player()
        self.update_tile_info(tile)
        if self.on_life_started:
            self.on_life_started(tile)

    # --- day planning ----------------------------------------------------

    def open_dropdown(self, idx, main_button):
        dropdown = self.action_dropdowns[idx][1]
        dropdown.clear_widgets()
        for action in available_actions(self.selected_actions, idx):
            btn = ThemedButton(
                text=action_option_text(action),
                markup=True,
                size_hint_y=None,
                height=34,
                halign="left",
                padding=[10, 0],
            )
            btn.bind(size=lambda b, size: setattr(b, "text_size", size))
            btn.bind(on_release=lambda btn, a=action: self.select_action(idx, a))
            dropdown.add_widget(btn)
        if self.selected_actions[idx]:
            clear = ThemedButton(text="— clear —", size_hint_y=None, height=34)
            clear.bind(on_release=lambda *_: self.select_action(idx, None))
            dropdown.add_widget(clear)
        dropdown.open(main_button)

    def select_action(self, idx, action):
        main_button, dropdown = self.action_dropdowns[idx]
        self.selected_actions[idx] = action
        main_button.text = f"{action['name']} {action['hours']}h" if action else f"Action {idx + 1}"
        dropdown.dismiss()
        self.refresh_hours()

    def refresh_hours(self):
        planned = hours_used(self.selected_actions)
        self.hours_label.text = f"{heading('Today')}  {muted(f'{planned} / {DAY_HOURS} h planned')}"
        for i, (main_button, _) in enumerate(self.action_dropdowns):
            # A slot is usable if it already has a pick (so it can be changed or
            # cleared) or something still fits in it.
            main_button.disabled = self.player is None or not (
                self.selected_actions[i] or available_actions(self.selected_actions, i)
            )

    def reset_plan(self):
        for i in range(ACTION_SLOTS):
            self.select_action(i, None)

    # --- turns -----------------------------------------------------------

    def on_take_action(self, instance):
        self.turn += 1
        actions_taken = [a["id"] for a in self.selected_actions if a]
        effects = []
        if self.game_map and self.player:
            regenerate_resources(self.game_map)
            effects = process_player_actions(self.player, actions_taken)
        self.add_log(format_effects(self.turn, effects))
        self.reset_plan()
        self.refresh_player()
        if self.selected_tile:
            self.update_tile_info(self.selected_tile)
        if self.player and self.player.state.health <= 0:
            app = App.get_running_app()
            if hasattr(app, "game_over"):
                app.game_over(self.death_summary())

    def death_summary(self):
        family = self.player.family
        return {
            "name": self.player.name,
            "family": family.name,
            "home": family.home.get("biome"),
            "days": self.turn,
            "karma": self.player.karma,
            "cause": "health reached 0",
        }

    def add_log(self, line):
        self.log_lines.insert(0, line)
        del self.log_lines[LOG_LENGTH:]
        self.log_label.text = "\n".join(self.log_lines)

    # --- display ---------------------------------------------------------

    def refresh_player(self):
        self.player_label.text = format_player_info(self.player)
        if self.player:
            self.turn_label.text = heading(f"Day {self.turn}")
            health = self.player.state.health
            karma = self.player.karma
            self.health_bar.set(f"{health:.0f}", health, GOOD if health > 30 else BAD)
            self.karma_bar.set(
                f"{karma:+.2f}".replace("-", "−"), karma, ACCENT if karma >= 0 else BAD
            )
        else:
            self.health_bar.set("—", 0, GOOD)
            self.karma_bar.set("—", 0, ACCENT)

    def update_tile_info(self, tile):
        self.selected_tile = tile
        home = self.player.family.home if self.player else None
        self.tile_label.text = format_tile_info(tile, home)
