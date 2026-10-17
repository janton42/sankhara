from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from sankhara.ui.theme import ACCENT, MUTED, PANEL, TEXT, AccentButton, ThemedButton, WrapLabel

ABOUT_TEXT = (
    "Sankhara is a game of karma and rebirth. You are born into a family "
    "somewhere in a generated world, and each day you choose how to spend your "
    "24 hours.\n\n"
    "Your choices shape your health and your karma. Sankhāra is the Pali word "
    "for the mental formations that, in Buddhist thought, condition what comes next."
)


class MainMenuScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.spacing = 16
        self.padding = [100, 60, 100, 60]
        self.add_widget(Label(size_hint_y=0.3))  # Top spacer
        self.title_label = Label(
            text="[b]Sankhara[/b]",
            markup=True,
            font_size=56,
            color=ACCENT,
            size_hint_y=None,
            height=80,
        )
        self.add_widget(self.title_label)
        self.subtitle_label = Label(
            text="a game of karma and rebirth",
            font_size=18,
            color=MUTED,
            size_hint_y=None,
            height=30,
        )
        self.add_widget(self.subtitle_label)
        self.add_widget(Label(size_hint_y=None, height=20))
        button_kwargs = {
            "size_hint": (None, None),
            "size": (320, 56),
            "pos_hint": {"center_x": 0.5},
        }
        self.new_game_btn = AccentButton(text="New Game", font_size=22, bold=True, **button_kwargs)
        self.add_widget(self.new_game_btn)
        self.about_btn = ThemedButton(text="About", font_size=20, **button_kwargs)
        self.about_btn.bind(on_press=lambda *_: self.show_about())
        self.add_widget(self.about_btn)
        self.add_widget(Label(size_hint_y=0.4))  # Bottom spacer

    def show_about(self):
        content = BoxLayout(orientation="vertical", spacing=12, padding=12)
        content.add_widget(WrapLabel(text=ABOUT_TEXT, color=TEXT))
        content.add_widget(Label())
        close_btn = ThemedButton(text="Close", size_hint_y=None, height=44)
        content.add_widget(close_btn)
        popup = Popup(
            title="About Sankhara",
            content=content,
            size_hint=(None, None),
            size=(520, 340),
            title_color=ACCENT,
            background="",
            background_color=PANEL,
            separator_color=ACCENT,
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
