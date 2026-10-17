"""The main game screen: who you are (left), the land (centre), and your year (right)."""

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from sankhara.sim import discoveries, game, projects
from sankhara.sim.people import family_of
from sankhara.sim.peoples import relation_word
from sankhara.sim.stations import ACTION_SLOTS, station_title
from sankhara.sim.world import game_map
from sankhara.ui.screens.map_view import MapScreen
from sankhara.ui.theme import (
    ACCENT,
    ACCENT_HEX,
    BUTTON,
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
    cohesion_word,
    cost_text,
    food_word,
    health_word,
    lore_word,
    plenty_word,
    population_text,
    regard_word,
    years_text,
)

CHRONICLE_LENGTH = 60
PULL_TINT = 0.25  # how strong an inclination must be before it shows in the chooser
# how long a year lasts when the years are left to pass, in seconds
PACES = (("unhurried", 7.0), ("steady", 3.5), ("swift", 1.5))
NEWS_LINGER = 2.0  # a year that brought news lasts this many times longer, to give time to react
TICK = 1 / 20
NOTICES_SHOWN = 5
WORK_NAMES = {
    "gathering": "a gathering place",
    "pits": "store pits",
    "fields": "fields",
    "weir": "a fish weir",
    "herd": "herds",
    "sacred": "a sacred place",
    "paths": "paths to the other camps",
}
SECTIONS = {
    "obligation": "Expected of you",
    "continue": "What you are working on",
    "join": "The people's works under way",
    "rally": "Call others to your work",
    "project": "Begin something for the people",
    "personal": "For yourself and your family",
    "deed": "This year",
}
WORKS_SHOWN = 6


def _section(parent, title):
    parent.add_widget(WrapLabel(text=heading(title)))
    label = WrapLabel(text="")
    parent.add_widget(label)
    return label


def _scrolling(widgets):
    rows = BoxLayout(orientation="vertical", spacing=4, size_hint_y=None)
    rows.bind(minimum_height=rows.setter("height"))
    for w in widgets:
        rows.add_widget(w)
    scroll = ScrollView(do_scroll_x=False)
    scroll.add_widget(rows)
    return scroll


class CharacterPanel(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=4, padding=[14, 12], **kwargs)
        fill_background(self, PANEL)
        self.state = None
        self.name_label = WrapLabel(text="", font_size=20)
        self.add_widget(self.name_label)
        self.who_label = WrapLabel(text="")
        self.add_widget(self.who_label)
        self.means_label = _section(self, "Means")
        self.family_label = _section(self, "Family")
        self.people_label = _section(self, "Your people")
        self.knowledge_button = ThemedButton(text="What we know", size_hint_y=None, height=36)
        self.knowledge_button.bind(on_release=lambda *_: self.show_knowledge())
        self.add_widget(self.knowledge_button)
        self.add_widget(Label())  # push content to the top

    def refresh(self, state):
        self.state = state
        p = state.player
        nation = state.nation
        home = state.settlement(p.settlement_id) or state.seat
        self.name_label.text = heading(p.full_name)
        self.who_label.text = (
            f"{station_title(p, nation)}, aged {p.age(state.year)}, of {home.name}\n"
            f"{muted('You feel')} {health_word(p.health)}  ·  "
            f"{muted('you are')} {regard_word(p.means.get('regard'))}"
        )
        means = f"Your family  {budget_text(p.means, nation)}"
        if p.station == "leader":
            means = f"Held in common  {budget_text(nation.stores, nation)}\n{means}"
        self.means_label.text = means

        family = family_of(state, p)
        if family:
            self.family_label.text = "\n".join(
                f"{muted(rel)}  {c.full_name} ({c.age(state.year)})" for rel, c in family
            )
        else:
            self.family_label.text = muted("You have no living family.")

        leader = state.leader
        if leader and not leader.is_player:
            led = f"Led by {leader.full_name}, aged {leader.age(state.year)}"
        else:
            led = "You lead them"
        pop = state.total_population()
        food = sum(s.food_balance for s in state.settlements.values())
        kinds = {s.kind for s in state.settlements.values()}
        place = "villages" if kinds == {"village"} else "camps"
        self.people_label.text = "\n".join(
            [
                f"[b]The {nation.name}[/b]  ·  {led}",
                f"{population_text(pop)} people in {len(state.settlements)} {place}  ·  "
                f"food: {food_word(food, pop)}",
                f"They are {cohesion_word(nation.cohesion)} and {plenty_word(nation.plenty)}",
                f"Their lore is {lore_word(nation.lore)}",
            ]
        )

    def show_knowledge(self):
        if self.state is not None:
            KnowledgePopup(self.state).open()


class KnowledgePopup(Popup):
    """What the people know, what is stirring, and who they have met."""

    def __init__(self, state, **kwargs):
        nation = state.nation
        widgets = [WrapLabel(text=heading("What the people know"))]
        for did, form_id in nation.known.items():
            d = discoveries.DISCOVERIES[did]
            form = d.form(form_id)
            title = f"[b]{d.name}[/b]" + (f": {form.name.lower()}" if form else "")
            text = form.text if form else d.text
            widgets.append(WrapLabel(text=f"{title}\n{muted(text)}", font_size=14))
        stirring = discoveries.stirring(state)
        widgets.append(WrapLabel(text="\n" + heading("Stirring among the people")))
        if not stirring:
            widgets.append(WrapLabel(text=muted("Nothing new, for now.")))
        for d in stirring:
            word = discoveries.progress_word(discoveries.progress(state, d))
            widgets.append(WrapLabel(text=f"{d.hint}\n{muted(word)}", font_size=14))
        met = [n for n in state.neighbours.values() if n.met]
        widgets.append(WrapLabel(text="\n" + heading("Other peoples")))
        if not met:
            widgets.append(WrapLabel(text=muted("No one has come from beyond our lands yet.")))
        for n in met:
            widgets.append(
                WrapLabel(
                    text=f"[b]The {n.name}[/b]  ·  {relation_word(n.relations)}  ·  "
                    f"about {population_text(round(n.population, -1))} people",
                    font_size=14,
                )
            )
        content = BoxLayout(orientation="vertical", spacing=8, padding=[10, 8])
        content.add_widget(_scrolling(widgets))
        close = ThemedButton(text="Close", size_hint_y=None, height=44)
        content.add_widget(close)
        super().__init__(
            title=f"The {nation.name}",
            content=content,
            size_hint=(0.6, 0.86),
            title_color=ACCENT,
            background="",
            background_color=PANEL,
            separator_color=ACCENT,
            **kwargs,
        )
        close.bind(on_release=lambda *_: self.dismiss())


class FormChoicePopup(Popup):
    """Something new is understood, and the player decides what shape it takes."""

    def __init__(self, state, on_chosen, **kwargs):
        self.state = state
        self.on_chosen = on_chosen
        d = discoveries.DISCOVERIES[state.pending_choice]
        deciding = state.pending_mode == "decide"
        question = (
            "How should it be among our people?"
            if deciding
            else "The people are deciding how it should be. What will you speak for?"
        )
        content = BoxLayout(orientation="vertical", spacing=8, padding=[10, 8])
        content.add_widget(WrapLabel(text=f"{d.text}\n\n{muted(question)}"))
        for form in d.forms:
            label = form.name if deciding else f"Speak for: {form.name.lower()}"
            btn = ThemedButton(
                text=f"[b]{label}[/b]\n{muted(form.text)}",
                markup=True,
                size_hint_y=None,
                height=64,
                halign="left",
                valign="middle",
                padding=[12, 4],
            )
            btn.bind(size=lambda b, size: setattr(b, "text_size", (size[0] - 24, None)))
            btn.bind(on_release=lambda _, f=form.id: self._choose(f))
            content.add_widget(btn)
        content.add_widget(Label())
        super().__init__(
            title=d.name,
            content=content,
            size_hint=(0.55, 0.7),
            auto_dismiss=False,
            title_color=ACCENT,
            background="",
            background_color=PANEL,
            separator_color=ACCENT,
            **kwargs,
        )

    def _choose(self, form_id):
        game.choose_form(self.state, form_id)
        self.dismiss()
        self.on_chosen()


class ChooserPopup(Popup):
    """Pick what to give a slot's attention to."""

    def __init__(self, state, slot, on_pick, **kwargs):
        self.state = state
        self.slot = slot
        self.on_pick = on_pick
        widgets = []
        section = None
        for opt in game.options(state):
            if opt.kind != section:
                section = opt.kind
                widgets.append(WrapLabel(text=heading(SECTIONS[section]), font_size=14))
            widgets.append(self._row(opt))
        content = BoxLayout(orientation="vertical", spacing=4, padding=[8, 8])
        content.add_widget(_scrolling(widgets))
        bottom = BoxLayout(size_hint_y=None, height=44, spacing=8)
        clear = ThemedButton(text="Leave this free")
        clear.bind(on_release=lambda *_: self._pick(None))
        close = ThemedButton(text="Cancel")
        close.bind(on_release=lambda *_: self.dismiss())
        bottom.add_widget(clear)
        bottom.add_widget(close)
        content.add_widget(bottom)
        super().__init__(
            title=f"Your attention ({slot + 1} of {len(state.plan)})",
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
        nation = state.nation
        taken_elsewhere = opt.key in state.plan and state.plan.index(opt.key) != self.slot
        can = game.affordable(state, opt, self.slot) and not taken_elsewhere
        cost = cost_text(opt.cost, nation)
        if opt.cost and state.player.station == "leader":
            cost += " (common)" if opt.scope == "people" else " (yours)"
        if opt.kind in ("continue", "join"):
            cost = f"about {years_text(opt.years)} more  ·  {cost} a year"
        elif opt.kind in ("project", "personal"):
            about = opt.project.definition.id == "pursue"
            cost = f"{years_text(opt.years, about=about)}  ·  {cost} a year"
        name = f"[b]{opt.name}[/b]"
        if opt.kind == "obligation":
            name = f"[color={ACCENT_HEX}]{name}[/color]  {muted(opt.blurb)}"
        elif opt.thread:
            worked = ", ".join(opt.project.worked_by)
            name = f"[color={ACCENT_HEX}]{name}[/color]  {muted('worked on by ' + worked)}"
        detail = muted(f"{opt.text}  ·  {cost}")
        if taken_elsewhere:
            detail += muted("  ·  already planned")
        btn = ThemedButton(
            text=f"{name}\n{detail}",
            markup=True,
            size_hint_y=None,
            height=58,
            halign="left",
            valign="middle",
            padding=[12, 6],
            disabled=not can,
        )
        # grow to fit however many lines the text wraps to
        btn.bind(texture_size=lambda b, ts: setattr(b, "height", max(52, ts[1] + 14)))
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


class YearBar(Widget):
    """A thin bar showing how much of the year has passed."""

    def __init__(self, **kwargs):
        super().__init__(size_hint_y=None, height=6, **kwargs)
        self.value = 0.0
        with self.canvas:
            Color(*BUTTON)
            self._track = Rectangle()
            Color(*ACCENT)
            self._fill = Rectangle()
        self.bind(pos=self._draw, size=self._draw)

    def set_value(self, value):
        self.value = max(0.0, min(1.0, value))
        self._draw()

    def _draw(self, *_):
        self._track.pos = self._fill.pos = self.pos
        self._track.size = self.size
        self._fill.size = (self.width * self.value, self.height)


class YearPanel(BoxLayout):
    def __init__(self, on_step, on_auto, on_pace, **kwargs):
        super().__init__(orientation="vertical", spacing=6, padding=[14, 12], **kwargs)
        fill_background(self, PANEL)
        self.state = None
        self.notices = []  # (year, text), newest last
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
        buttons = BoxLayout(size_hint_y=None, height=44, spacing=8)
        self.auto_button = AccentButton(text="Let the years pass", bold=True, size_hint_x=1.4)
        self.auto_button.bind(on_release=lambda *_: on_auto())
        self.end_button = ThemedButton(text="One year")
        self.end_button.bind(on_release=lambda *_: on_step())
        self.pace_button = ThemedButton(text="", font_size=13)
        self.pace_button.bind(on_release=lambda *_: on_pace())
        buttons.add_widget(self.auto_button)
        buttons.add_widget(self.end_button)
        buttons.add_widget(self.pace_button)
        self.add_widget(buttons)
        self.bar = YearBar()
        self.add_widget(self.bar)
        self.notice_label = WrapLabel(text="", font_size=13)
        self.add_widget(self.notice_label)
        self.add_widget(WrapLabel(text=heading("Chronicle")))
        self.chronicle = WrapLabel(text="", font_size=13)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.chronicle)
        self.add_widget(scroll)

    def add_notices(self, year, texts):
        self.notices += [(year, t) for t in texts]
        del self.notices[:-NOTICES_SHOWN]

    def refresh(self, state):
        self.state = state
        nation = state.nation
        self.year_label.text = heading(f"Year {state.year}")
        if state.events:
            self.events_label.text = "\n".join(f"• {e.text}" for e in state.events)
        else:
            self.events_label.text = muted("Nothing out of the ordinary.")
        for i, btn in enumerate(self.slot_buttons):
            key = state.plan[i] if i < len(state.plan) else None
            opt = game.option_for(state, key) if key else None
            if opt:
                mark = f"[color={ACCENT_HEX}]•[/color] " if opt.kind == "obligation" else ""
                text = f"{mark}{opt.name}"
                if opt.kind == "continue":
                    p = opt.project
                    word = projects.progress_word(projects.progress(state, p))
                    helping = p.leader_id != state.player_id
                    text += muted(f"  ·  {'helping, ' if helping else ''}{word}")
                elif opt.kind in ("project", "personal", "join"):
                    text += muted("  ·  new")
                btn.text = text
                btn.color = TEXT
            else:
                btn.text = "— free —"
                btn.color = MUTED
        stores, own = game.remaining_budget(state)
        if state.player.station == "leader":
            left = f"Common stores after plans: {budget_text(stores, nation)}\n"
        else:
            left = ""
        left += f"Your family after plans: {budget_text(own, nation)}"
        lines = [muted(left)]
        unmet = [
            e
            for i, e in enumerate(state.events)
            if e.obligation
            and f"event:{i}" not in state.plan
            and e.obligation not in state.plan
            and not any(k in state.plan for k in e.data.get("also", []))
        ]
        if unmet:
            lines.append(f"[color={ACCENT_HEX}]Something is expected of you this year.[/color]")
        self.left_label.text = "\n".join(lines)
        self.notice_label.text = "\n".join(
            f"{muted(f'Year {year}')}  [color={ACCENT_HEX}]{text}[/color]"
            for year, text in reversed(self.notices)
        )
        self.chronicle.text = "\n".join(reversed(state.log[-CHRONICLE_LENGTH:]))

    def set_running(self, running, pace):
        self.auto_button.text = "Pause" if running else "Let the years pass"
        self.end_button.disabled = running
        self.pace_button.text = f"Pace: {pace}"
        if not running:
            self.bar.set_value(0)

    def open_chooser(self, slot):
        if self.state is not None:
            ChooserPopup(self.state, slot, on_pick=lambda: self.refresh(self.state)).open()


def works_text(state):
    """The people's works under way: what, who leads, how far along. Yours are marked."""
    works = [p for p in state.projects.values() if p.common]
    if not works:
        return muted("Nothing is being built or worked out in common.")
    me = state.player_id

    def order(p):
        return (me not in (p.leader_id, *p.helpers), not p.worked_by, -projects.progress(state, p))

    rows = []
    for p in sorted(works, key=order)[:WORKS_SHOWN]:
        leader = state.character(p.leader_id)
        if p.leader_id == me:
            who = "you"
        elif leader:
            who = leader.full_name
        else:
            who = "no one"
        helpers = len(p.helpers) + (1 if p.support > 0.5 else 0)
        crowd = f", {helpers} helping" if helpers else ""
        word = projects.progress_word(projects.progress(state, p))
        name = projects.display_name(state, p)
        mark = f"[color={ACCENT_HEX}]•[/color] " if me in (p.leader_id, *p.helpers) else "• "
        rows.append(f"{mark}{name}  {muted(f'· {who}{crowd} · {word}')}")
    if len(works) > WORKS_SHOWN:
        rows.append(muted(f"and {len(works) - WORKS_SHOWN} more"))
    return "\n".join(rows)


class GameView(BoxLayout):
    """Holds the current GameState and wires the panels to the simulation."""

    def __init__(self, on_life_ended, on_saved, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)
        self.state = None
        self.on_life_ended = on_life_ended
        self.on_saved = on_saved
        self.auto_event = None
        self.choice_popup = None
        self.pace = 1
        self.elapsed = 0.0
        self.year_length = PACES[self.pace][1]
        self.resume_after_life = False
        self.character = CharacterPanel(size_hint_x=0.27)
        self.add_widget(self.character)
        centre = BoxLayout(orientation="vertical", size_hint_x=0.43, padding=[4, 8], spacing=4)
        self.map_view = MapScreen(on_tile_selected_callback=self.on_tile_selected)
        centre.add_widget(self.map_view)
        self.tile_label = WrapLabel(text="", font_size=13, color=TEXT)
        centre.add_widget(self.tile_label)
        centre.add_widget(WrapLabel(text=heading("The people's works")))
        self.works_label = WrapLabel(text="", font_size=13)
        centre.add_widget(self.works_label)
        self.add_widget(centre)
        self.year = YearPanel(
            on_step=self.end_year,
            on_auto=self.toggle_auto,
            on_pace=self.change_pace,
            size_hint_x=0.30,
        )
        self.add_widget(self.year)
        self.year.set_running(False, PACES[self.pace][0])

    def set_state(self, state):
        resume = self.resume_after_life and self.state is state
        self.resume_after_life = False
        self.stop_auto()
        self.state = state
        self.year.notices = []
        self.map_view.set_map(game_map(state))
        self.refresh()
        if resume and not state.life_over:
            self.start_auto()

    def refresh(self):
        state = self.state
        settlements = [(s.col, s.row, s.population, s.is_seat) for s in state.settlements.values()]
        home = state.settlement(state.player.settlement_id) or state.seat
        others = [
            (n.territory, (n.col, n.row), n.population) for n in state.neighbours.values() if n.met
        ]
        self.map_view.set_realm(
            state.nation.territory, settlements, home=(home.col, home.row), others=others
        )
        self.character.refresh(state)
        self.year.refresh(state)
        self.works_label.text = works_text(state)
        if self.map_view.selected_tile:
            self.on_tile_selected(self.map_view.selected_tile)
        else:
            self.tile_label.text = muted("Click the map to look at a place.")
        if state.pending_choice and not state.life_over:
            self.ask_form()

    def ask_form(self):
        """A pop-up is the one thing that holds the years until the player answers."""
        if self.choice_popup is not None:
            return
        self.choice_popup = FormChoicePopup(self.state, on_chosen=self._form_chosen)
        self.choice_popup.open()

    def _form_chosen(self):
        self.choice_popup = None
        self.on_saved(self.state)
        self.refresh()

    def on_tile_selected(self, tile):
        state = self.state
        cell = (tile["q"], tile["r"])
        here = next((s for s in state.settlements.values() if (s.col, s.row) == cell), None)
        if here:
            works = ", ".join(
                WORK_NAMES.get(k, k) + (f" ×{v}" if v > 1 else "")
                for k, v in sorted(here.works.items())
                if v
            )
            kind = "where the leader lives" if here.is_seat else f"a {here.kind}"
            self.tile_label.text = (
                f"[b]{here.name}[/b], {kind}  ·  {tile['biome']}\n"
                f"{population_text(here.population)} people  ·  food: "
                f"{food_word(here.food_balance, here.population)}  ·  "
                f"{cohesion_word(here.cohesion)}, {plenty_word(here.plenty)}"
                + (f"\n{muted('They have ' + works)}" if works else "")
            )
            return
        if list(cell) in state.nation.territory:
            self.tile_label.text = f"{tile['biome']}  ·  " + muted("our people's land")
            return
        owner = next(
            (n for n in state.neighbours.values() if n.met and list(cell) in n.territory), None
        )
        if owner:
            self.tile_label.text = (
                f"{tile['biome']}  ·  land of the {owner.name}, "
                f"{muted(relation_word(owner.relations))}"
            )
        else:
            self.tile_label.text = f"{tile['biome']}  ·  " + muted("land we do not know")

    def end_year(self, attended=True):
        if self.state.life_over:
            return None
        if self.state.pending_choice:
            self.ask_form()
            return None
        report = game.end_year(self.state, attended=attended)
        self.on_saved(self.state)
        self.year.add_notices(report.year, report.interrupts)
        if report.life_ended:
            self.resume_after_life = self.auto_event is not None
            self.stop_auto()
            self.on_life_ended(self.state)
        else:
            self.refresh()
        return report

    # --- letting the years pass -------------------------------------------------
    #
    # The years run on their own until the player pauses them. News doesn't stop them;
    # a year that brought some lasts longer, so there is time to pause and act. Only a
    # pop-up (or the player looking into something) holds the year until it closes.

    def toggle_auto(self):
        if self.auto_event is not None:
            self.stop_auto()
        else:
            self.start_auto()

    def start_auto(self):
        self.elapsed = 0.0
        self.year_length = PACES[self.pace][1]
        self.auto_event = Clock.schedule_interval(self._tick, TICK)
        self.year.set_running(True, PACES[self.pace][0])

    def stop_auto(self):
        if self.auto_event is not None:
            self.auto_event.cancel()
            self.auto_event = None
        self.year.set_running(False, PACES[self.pace][0])

    def change_pace(self):
        self.pace = (self.pace + 1) % len(PACES)
        self.year_length = PACES[self.pace][1]
        self.year.set_running(self.auto_event is not None, PACES[self.pace][0])

    def held(self):
        """Something is open that the year waits for."""
        return self.state.pending_choice is not None or any(
            isinstance(w, ModalView) for w in Window.children
        )

    def _tick(self, dt):
        if self.held():
            return
        self.elapsed += dt
        self.year.bar.set_value(self.elapsed / self.year_length)
        if self.elapsed >= self.year_length:
            self.auto_step()

    def auto_step(self):
        """One year passing on its own."""
        self.elapsed = 0.0
        report = self.end_year(attended=False)
        pace = PACES[self.pace][1]
        self.year_length = pace * (NEWS_LINGER if report and report.interrupts else 1)
        self.year.bar.set_value(0)
        return report
