from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label


class GameOverScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.spacing = 40
        self.padding = [100, 100, 100, 100]
        self.add_widget(Label(text="", size_hint_y=0.3))  # Top spacer
        self.game_over_label = Label(
            text="[b]Game Over[/b]", markup=True, font_size=48, size_hint_y=0.3
        )
        self.add_widget(self.game_over_label)
        self.add_widget(Label(text="", size_hint_y=0.1))  # Spacer below title
        self.main_menu_btn = Button(text="Return to Main Menu", size_hint_y=0.15, font_size=24)
        self.add_widget(self.main_menu_btn)
        self.add_widget(Label(text="", size_hint_y=0.2))  # Bottom spacer
