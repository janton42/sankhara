"""Between lives: how one life ended, then how the next begins."""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from sankhara.ui.theme import ACCENT, AccentButton, ThemedButton, WrapLabel, muted


def format_life(life):
    return "\n".join(
        [
            f"[b]{life['name']}[/b]",
            f"{life['station']} of {life['settlement']}",
            f"Year {life['born']} to year {life['died']}, aged {life['age']}",
            muted(f"Died of {life['cause']}"),
        ]
    )


def format_earlier_lives(lives):
    if not lives:
        return ""
    rows = [
        f"{life['name']}  ·  {life['station'].lower()}  ·  years {life['born']}–{life['died']}"
        for life in lives
    ]
    return muted("Before:\n" + "\n".join(rows))


class LifeScreen(BoxLayout):
    def __init__(self, on_continue, on_begin, on_menu, **kwargs):
        super().__init__(orientation="vertical", spacing=14, padding=[140, 40], **kwargs)
        self.on_continue = on_continue
        self.on_begin = on_begin
        self.title = Label(
            text="", markup=True, font_size=36, color=ACCENT, size_hint_y=None, height=60
        )
        self.add_widget(self.title)
        self.body = WrapLabel(text="", font_size=17, halign="center")
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.body)
        self.add_widget(scroll)
        buttons = BoxLayout(
            size_hint=(None, None), size=(560, 56), spacing=16, pos_hint={"center_x": 0.5}
        )
        self.primary = AccentButton(text="", font_size=20, bold=True)
        self.primary.bind(on_release=lambda *_: self._primary())
        self.menu_btn = ThemedButton(text="Main Menu", font_size=18)
        self.menu_btn.bind(on_release=lambda *_: on_menu())
        buttons.add_widget(self.primary)
        buttons.add_widget(self.menu_btn)
        self.add_widget(buttons)
        self.stage = "death"

    def show_death(self, state):
        self.stage = "death"
        life = state.soul.lives[-1]
        self.title.text = "[b]A life has ended[/b]"
        earlier = format_earlier_lives(state.soul.lives[:-1])
        self.body.text = format_life(life) + ("\n\n\n" + earlier if earlier else "")
        self.primary.text = "Continue"

    def show_birth(self, lines):
        self.stage = "birth"
        self.title.text = "[b]A life begins[/b]"
        self.body.text = "\n\n".join(lines)
        self.primary.text = "Begin"

    def _primary(self):
        if self.stage == "death":
            self.on_continue()
        else:
            self.on_begin()
