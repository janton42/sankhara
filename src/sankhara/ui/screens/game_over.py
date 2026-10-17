from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from sankhara.ui.theme import ACCENT, TEXT, AccentButton, muted


def format_summary(summary):
    if not summary:
        return ""
    karma = f"{summary['karma']:+.2f}".replace("-", "−")
    return "\n".join(
        [
            f"[b]{summary['name']}[/b] of the {summary['family']} family",
            muted(f"born in the {summary['home']}"),
            "",
            f"Lived {summary['days']} days  ·  final karma {karma}",
            muted(f"Cause of death: {summary['cause']}"),
        ]
    )


class GameOverScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.spacing = 20
        self.padding = [100, 60, 100, 60]
        self.add_widget(Label(size_hint_y=0.2))  # Top spacer
        self.game_over_label = Label(
            text="[b]This life has ended[/b]",
            markup=True,
            font_size=40,
            color=ACCENT,
            size_hint_y=None,
            height=60,
        )
        self.add_widget(self.game_over_label)
        self.summary_label = Label(
            text="",
            markup=True,
            font_size=18,
            color=TEXT,
            halign="center",
            size_hint_y=None,
            height=140,
        )
        self.add_widget(self.summary_label)
        self.main_menu_btn = AccentButton(
            text="Return to Main Menu",
            font_size=20,
            size_hint=(None, None),
            size=(320, 56),
            pos_hint={"center_x": 0.5},
        )
        self.add_widget(self.main_menu_btn)
        self.add_widget(Label(size_hint_y=0.3))  # Bottom spacer

    def set_summary(self, summary):
        self.summary_label.text = format_summary(summary)
