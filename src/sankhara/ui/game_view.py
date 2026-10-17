"""The main game screen: who you are (left), the realm (centre), and your year (right)."""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from sankhara.sim import game
from sankhara.sim.actions import budget_for
from sankhara.sim.people import family_of
from sankhara.sim.stations import ACTION_SLOTS, STATIONS, station_title
from sankhara.sim.world import game_map
from sankhara.ui.screens.map_view import MapScreen
from sankhara.ui.theme import (
    ACCENT,
    ACCENT_HEX,
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
from sankhara.ui.words import (
    budget_text,
    cost_text,
    harvest_word,
    health_word,
    level_word,
    population_text,
    prosperity_word,
    stability_word,
)

CHRONICLE_LENGTH = 60
PULL_TINT = 0.25  # how strong an inclination must be before it shows in the chooser


def _section(parent, title):
    parent.add_widget(WrapLabel(text=heading(title)))
    label = WrapLabel(text="")
    parent.add_widget(label)
    return label


class CharacterPanel(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=4, padding=[14, 12], **kwargs)
        fill_background(self, PANEL)
        self.name_label = WrapLabel(text="", font_size=20)
        self.add_widget(self.name_label)
        self.who_label = WrapLabel(text="")
        self.add_widget(self.who_label)
        self.means_label = _section(self, "Means")
        self.family_label = _section(self, "Family")
        self.realm_label = _section(self, "Realm")
        self.add_widget(Label())  # push content to the top

    def refresh(self, state):
        p = state.player
        nation = state.nation
        home = state.settlement(p.settlement_id)
        title = station_title(p, nation)
        self.name_label.text = heading(p.full_name)
        self.who_label.text = (
            f"{title}, aged {p.age(state.year)}, of {home.name}\n"
            f"{muted('You feel')} {health_word(p.health)}"
        )

        if p.station == "ruler":
            means = (
                f"Treasury  {budget_text(nation.treasury)}\nHousehold  {budget_text(p.household)}"
            )
        else:
            means = f"{STATIONS[p.station].household_title}  {budget_text(p.household)}"
        self.means_label.text = means

        family = family_of(state, p)
        if family:
            self.family_label.text = "\n".join(
                f"{muted(rel)}  {c.full_name} ({c.age(state.year)})" for rel, c in family
            )
        else:
            self.family_label.text = muted("You have no living family.")

        ruler = state.ruler
        if ruler and not ruler.is_player:
            rule = f"Ruled by {ruler.full_name}, aged {ruler.age(state.year)}"
        else:
            rule = "You rule"
        pop = state.total_population()
        food = sum(s.food_balance for s in state.settlements.values())
        self.realm_label.text = "\n".join(
            [
                f"[b]{nation.name}[/b]  ·  {rule}",
                f"{population_text(pop)} people  ·  harvest: {harvest_word(food, pop)}",
                f"The people are {stability_word(nation.stability)} and "
                f"{prosperity_word(nation.prosperity)}",
                f"Learning {level_word(nation.learning)}  ·  arts {level_word(nation.arts)}",
                f"Taxes {nation.tax_rate:.0%}",
            ]
        )


class ChooserPopup(Popup):
    """Pick what to give a slot's attention to this year."""

    def __init__(self, state, slot, on_pick, **kwargs):
        self.state = state
        self.slot = slot
        self.on_pick = on_pick
        content = BoxLayout(orientation="vertical", spacing=4, padding=[8, 8])
        rows = BoxLayout(orientation="vertical", spacing=4, size_hint_y=None)
        rows.bind(minimum_height=rows.setter("height"))
        for opt in game.options(state):
            rows.add_widget(self._row(opt))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(rows)
        content.add_widget(scroll)
        bottom = BoxLayout(size_hint_y=None, height=44, spacing=8)
        clear = ThemedButton(text="Leave this free")
        clear.bind(on_release=lambda *_: self._pick(None))
        close = ThemedButton(text="Cancel")
        close.bind(on_release=lambda *_: self.dismiss())
        bottom.add_widget(clear)
        bottom.add_widget(close)
        content.add_widget(bottom)
        super().__init__(
            title=f"Your attention this year ({slot + 1} of {len(state.plan)})",
            content=content,
            size_hint=(0.62, 0.86),
            title_color=ACCENT,
            background="",
            background_color=PANEL,
            separator_color=ACCENT,
            **kwargs,
        )

    def _row(self, opt):
        state = self.state
        taken_elsewhere = opt.key in state.plan and state.plan.index(opt.key) != self.slot
        can = game.affordable(state, opt, self.slot) and not taken_elsewhere
        payer = budget_for(state, state.player, opt.action)
        source = "treasury" if payer is state.nation.treasury else "own"
        cost = cost_text(opt.cost) + (
            f" ({source})" if opt.cost and state.player.station == "ruler" else ""
        )
        name = f"[b]{opt.action.name}[/b]"
        if opt.obligation:
            name = f"[color={ACCENT_HEX}]{name}[/color]  {muted(opt.blurb)}"
        detail = muted(f"{opt.action.text}  ·  {cost}")
        if taken_elsewhere:
            detail += muted("  ·  already planned")
        btn = ThemedButton(
            text=f"{name}\n{detail}",
            markup=True,
            size_hint_y=None,
            height=58,
            halign="left",
            valign="middle",
            padding=[12, 4],
            disabled=not can,
        )
        # inclinations are felt, not labelled: what you lean toward reads warmer, what
        # goes against the grain reads dimmer
        if opt.pull > PULL_TINT:
            btn.color = (1.0, 0.95, 0.85, 1)
        elif opt.pull < -PULL_TINT:
            btn.color = MUTED
        btn.bind(size=lambda b, size: setattr(b, "text_size", (size[0] - 24, None)))
        btn.bind(on_release=lambda *_: self._pick(opt.key))
        return btn

    def _pick(self, key):
        if game.choose(self.state, self.slot, key):
            self.dismiss()
            self.on_pick()


class YearPanel(BoxLayout):
    def __init__(self, on_end_year, **kwargs):
        super().__init__(orientation="vertical", spacing=6, padding=[14, 12], **kwargs)
        fill_background(self, PANEL)
        self.state = None
        self.year_label = WrapLabel(text="", font_size=20)
        self.add_widget(self.year_label)
        self.events_label = _section(self, "This year")
        self.add_widget(WrapLabel(text=heading("Your attention")))
        self.slot_buttons = []
        for i in range(ACTION_SLOTS):
            btn = ThemedButton(
                text="",
                size_hint_y=None,
                height=40,
                markup=True,
                shorten=True,
                shorten_from="right",
            )
            btn.bind(size=lambda b, size: setattr(b, "text_size", (size[0] - 16, None)))
            btn.bind(on_release=lambda _, i=i: self.open_chooser(i))
            self.add_widget(btn)
            self.slot_buttons.append(btn)
        self.left_label = WrapLabel(text="", font_size=13)
        self.add_widget(self.left_label)
        self.end_button = AccentButton(text="End the Year", size_hint_y=None, height=44, bold=True)
        self.end_button.bind(on_release=lambda *_: on_end_year())
        self.add_widget(self.end_button)
        self.add_widget(WrapLabel(text=heading("Chronicle")))
        self.chronicle = WrapLabel(text="", font_size=13)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.chronicle)
        self.add_widget(scroll)

    def refresh(self, state):
        self.state = state
        self.year_label.text = heading(f"Year {state.year}")
        if state.events:
            self.events_label.text = "\n".join(f"• {e.text}" for e in state.events)
        else:
            self.events_label.text = muted("Nothing out of the ordinary.")
        for i, btn in enumerate(self.slot_buttons):
            key = state.plan[i] if i < len(state.plan) else None
            opt = game.option_for(state, key) if key else None
            if opt:
                mark = f"[color={ACCENT_HEX}]•[/color] " if opt.obligation else ""
                btn.text = f"{mark}{opt.action.name}"
                btn.color = TEXT
            else:
                btn.text = "— free —"
                btn.color = MUTED
        treasury, household = game.remaining_budget(state)
        if state.player.station == "ruler":
            left = f"Treasury after plans: {budget_text(treasury)}"
        else:
            left = f"Left after plans: {budget_text(household)}"
        unmet = [
            e
            for i, e in enumerate(state.events)
            if e.obligation and f"event:{i}" not in state.plan and e.obligation not in state.plan
        ]
        if unmet:
            left += f"\n[color={ACCENT_HEX}]Something is expected of you this year.[/color]"
        self.left_label.text = muted(left) if not unmet else left
        self.chronicle.text = "\n".join(reversed(state.log[-CHRONICLE_LENGTH:]))

    def open_chooser(self, slot):
        if self.state is not None:
            ChooserPopup(self.state, slot, on_pick=lambda: self.refresh(self.state)).open()


class GameView(BoxLayout):
    """Holds the current GameState and wires the panels to the simulation."""

    def __init__(self, on_life_ended, on_saved, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)
        self.state = None
        self.on_life_ended = on_life_ended
        self.on_saved = on_saved
        self.character = CharacterPanel(size_hint_x=0.27)
        self.add_widget(self.character)
        centre = BoxLayout(orientation="vertical", size_hint_x=0.43, padding=[4, 8], spacing=4)
        self.map_view = MapScreen(on_tile_selected_callback=self.on_tile_selected)
        centre.add_widget(self.map_view)
        self.tile_label = WrapLabel(text="", font_size=13, color=TEXT)
        centre.add_widget(self.tile_label)
        self.add_widget(centre)
        self.year = YearPanel(on_end_year=self.end_year, size_hint_x=0.30)
        self.add_widget(self.year)

    def set_state(self, state):
        self.state = state
        self.map_view.set_map(game_map(state))
        self.refresh()

    def refresh(self):
        state = self.state
        settlements = [
            (s.col, s.row, s.population, s.is_capital) for s in state.settlements.values()
        ]
        home = state.settlement(state.player.settlement_id)
        self.map_view.set_realm(state.nation.territory, settlements, home=(home.col, home.row))
        self.character.refresh(state)
        self.year.refresh(state)
        if self.map_view.selected_tile:
            self.on_tile_selected(self.map_view.selected_tile)
        else:
            self.tile_label.text = muted("Click the map to look at a place.")

    def on_tile_selected(self, tile):
        state = self.state
        here = next(
            (s for s in state.settlements.values() if (s.col, s.row) == (tile["q"], tile["r"])),
            None,
        )
        inside = [tile["q"], tile["r"]] in state.nation.territory
        where = "within the realm" if inside else "beyond the borders"
        if here:
            works = ", ".join(f"{k} {v}" for k, v in sorted(here.works.items()) if v) or "none"
            kind = "the capital" if here.is_capital else "a town"
            self.tile_label.text = (
                f"[b]{here.name}[/b], {kind}  ·  {tile['biome']}\n"
                f"{population_text(here.population)} people  ·  harvest "
                f"{harvest_word(here.food_balance, here.population)}  ·  "
                f"{stability_word(here.stability)}, {prosperity_word(here.prosperity)}\n"
                + muted(f"Works: {works}")
            )
        else:
            self.tile_label.text = f"{tile['biome']}  ·  " + muted(where)

    def end_year(self):
        report = game.end_year(self.state)
        self.on_saved(self.state)
        if report.life_ended:
            self.on_life_ended(self.state)
        else:
            self.refresh()
