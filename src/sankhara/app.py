from pathlib import Path

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager

from sankhara.sim import game, save
from sankhara.ui.game_view import GameView
from sankhara.ui.screens.life import LifeScreen
from sankhara.ui.screens.main_menu import MainMenuScreen
from sankhara.ui.theme import BACKGROUND

SAVE_NAME = "save.json"


class SankharaApp(App):
    def build(self):
        self.title = "Sankhara"
        Window.size = (1280, 760)
        Window.minimum_width, Window.minimum_height = 1000, 640
        Window.clearcolor = BACKGROUND
        self.state = None

        self.menu = MainMenuScreen()
        self.menu.new_game_btn.bind(on_release=lambda *_: self.new_game())
        self.menu.continue_btn.bind(on_release=lambda *_: self.continue_game())
        self.game_view = GameView(on_life_ended=self.life_ended, on_saved=self.save)
        self.life = LifeScreen(
            on_continue=self.next_life, on_begin=self.show_game, on_menu=self.goto_menu
        )

        self.sm = ScreenManager(transition=FadeTransition(duration=0.2))
        for name, widget in (("menu", self.menu), ("game", self.game_view), ("life", self.life)):
            screen = Screen(name=name)
            screen.add_widget(widget)
            self.sm.add_widget(screen)
        self.goto_menu()
        return self.sm

    # --- saving --------------------------------------------------------------

    @property
    def save_path(self):
        return Path(self.user_data_dir) / SAVE_NAME

    def save(self, state):
        save.save(state, self.save_path)

    def has_save(self):
        return self.save_path.exists()

    # --- flow ------------------------------------------------------------------

    def goto_menu(self):
        self.menu.continue_btn.disabled = not self.has_save()
        self.sm.current = "menu"

    def new_game(self):
        self.state = game.new_game()
        self.save(self.state)
        self.show_game()

    def continue_game(self):
        try:
            self.state = save.load(self.save_path)
        except (OSError, ValueError, KeyError):
            self.menu.continue_btn.disabled = True
            return
        if self.state.life_over:
            self.life_ended(self.state)
        else:
            self.show_game()

    def show_game(self):
        self.game_view.set_state(self.state)
        self.sm.current = "game"

    def life_ended(self, state):
        self.life.show_death(state)
        self.sm.current = "life"

    def next_life(self):
        lines = game.begin_next_life(self.state)
        self.save(self.state)
        self.life.show_birth(lines)


def main():
    SankharaApp().run()


if __name__ == "__main__":
    main()
