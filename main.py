from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import ScreenManager, Screen

from ui.screens.map_view import MapScreen
from ui.ui_kivy import InfoPanel
from core.turn_manager import regenerate_resources, process_player_actions
from ui.screens.main_menu import MainMenuScreen
from ui.screens.game_over import GameOverScreen

class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'

        # Generate and store the game map at the top level
        from core.game_engine import generate_map
        self.game_map = generate_map()

        self.left_panel = InfoPanel(size_hint=(0.4, 1))
        self.left_panel.set_game_map(self.game_map)  # Pass map to InfoPanel
        self.add_widget(self.left_panel)

        self.right_panel = BoxLayout(orientation='vertical', size_hint=(0.6, 1))
        self.map_screen = MapScreen(on_tile_selected_callback=self.on_tile_selected)
        self.map_screen.map_data = self.game_map  # Use the shared map
        self.render_button = Button(text="Render Map", size_hint=(1, 0.1))
        self.render_button.bind(on_press=self.on_render_map)

        self.right_panel.add_widget(self.render_button)
        map_container = FloatLayout(size_hint=(1, 0.9))
        self.map_screen.size_hint = (0.8, 0.8)
        self.map_screen.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        map_container.add_widget(self.map_screen)
        self.right_panel.add_widget(map_container)
        self.add_widget(self.right_panel)

    def on_render_map(self, instance):
        self.map_screen.draw_map()

    def on_tile_selected(self, tile):
        self.left_panel.update_tile_info(tile)

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
        Window.size = (1024, 600)
        self.sm = ScreenManager()
        self.menu_screen = MainMenuKivyScreen(self.start_game, name='menu')
        self.game_screen = MainGameKivyScreen(name='game')
        self.game_over_screen = GameOverKivyScreen(self.goto_menu, name='gameover')
        self.sm.add_widget(self.menu_screen)
        self.sm.add_widget(self.game_screen)
        self.sm.add_widget(self.game_over_screen)
        self.sm.current = 'menu'
        return self.sm

    def start_game(self):
        # Reset game state (map, player, etc.)
        self.game_screen.reset_game()
        self.sm.current = 'game'

    def goto_menu(self):
        self.sm.current = 'menu'

    def game_over(self):
        self.sm.current = 'gameover'

if __name__ == '__main__':
    SankharaApp().run()
