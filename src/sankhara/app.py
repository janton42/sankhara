from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager

from sankhara.core.game_engine import generate_map, new_seed
from sankhara.ui.screens.game_over import GameOverScreen
from sankhara.ui.screens.main_menu import MainMenuScreen
from sankhara.ui.screens.map_view import MapScreen
from sankhara.ui.theme import BACKGROUND
from sankhara.ui.ui_kivy import InfoPanel


class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"

        # Generate and store the game map at the top level; a fresh seed per game
        self.seed = new_seed()
        self.game_map = generate_map(self.seed)

        self.left_panel = InfoPanel(size_hint=(0.38, 1), on_life_started=self.on_life_started)
        self.left_panel.set_game_map(self.game_map, self.seed)
        self.add_widget(self.left_panel)

        self.map_screen = MapScreen(
            on_tile_selected_callback=self.on_tile_selected, size_hint=(0.62, 1)
        )
        self.map_screen.set_map(self.game_map)
        self.add_widget(self.map_screen)

    def on_tile_selected(self, tile):
        self.left_panel.update_tile_info(tile)

    def on_life_started(self, home_tile):
        self.map_screen.selected_tile = home_tile
        self.map_screen.set_home(home_tile)


class MainMenuKivyScreen(Screen):
    def __init__(self, switch_to_game_callback, **kwargs):
        super().__init__(**kwargs)
        self.menu = MainMenuScreen()
        self.menu.new_game_btn.bind(on_press=lambda *_: switch_to_game_callback())
        self.add_widget(self.menu)


class GameOverKivyScreen(Screen):
    def __init__(self, switch_to_menu_callback, **kwargs):
        super().__init__(**kwargs)
        self.over = GameOverScreen()
        self.over.main_menu_btn.bind(on_press=lambda *_: switch_to_menu_callback())
        self.add_widget(self.over)


class MainGameKivyScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_screen = MainScreen()
        self.add_widget(self.main_screen)

    def reset_game(self):
        self.clear_widgets()
        self.main_screen = MainScreen()
        self.add_widget(self.main_screen)


class SankharaApp(App):
    def build(self):
        self.title = "Sankhara"
        Window.size = (1200, 740)
        Window.minimum_width, Window.minimum_height = 900, 600
        Window.clearcolor = BACKGROUND
        self.sm = ScreenManager(transition=FadeTransition(duration=0.2))
        self.menu_screen = MainMenuKivyScreen(self.start_game, name="menu")
        self.game_screen = MainGameKivyScreen(name="game")
        self.game_over_screen = GameOverKivyScreen(self.goto_menu, name="gameover")
        self.sm.add_widget(self.menu_screen)
        self.sm.add_widget(self.game_screen)
        self.sm.add_widget(self.game_over_screen)
        self.sm.current = "menu"
        return self.sm

    def start_game(self):
        # Reset game state (map, player, etc.)
        self.game_screen.reset_game()
        self.sm.current = "game"

    def goto_menu(self):
        self.sm.current = "menu"

    def game_over(self, summary=None):
        self.game_over_screen.over.set_summary(summary)
        self.sm.current = "gameover"


def main():
    SankharaApp().run()


if __name__ == "__main__":
    main()
