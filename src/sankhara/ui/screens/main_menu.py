from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label


class MainMenuScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.spacing = 40
        self.padding = [100, 100, 100, 100]
        self.add_widget(Label(text="", size_hint_y=0.2))  # Top spacer
        self.title_label = Label(text="[b]Sankhara[/b]", markup=True, font_size=48, size_hint_y=0.3)
        self.add_widget(self.title_label)
        self.add_widget(Label(text="", size_hint_y=0.1))  # Spacer below title
        self.new_game_btn = Button(text="New Game", size_hint_y=0.12, font_size=24)
        self.add_widget(self.new_game_btn)
        self.continue_btn = Button(
            text="Continue (placeholder)", size_hint_y=0.12, font_size=20, disabled=True
        )
        self.add_widget(self.continue_btn)
        self.about_btn = Button(
            text="About (placeholder)", size_hint_y=0.12, font_size=20, disabled=True
        )
        self.add_widget(self.about_btn)
        self.add_widget(Label(text="", size_hint_y=0.2))  # Bottom spacer
