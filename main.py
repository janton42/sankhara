from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.uix.textinput import TextInput

from ui.screens.map_view import MapScreen
from kivy.uix.floatlayout import FloatLayout

class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'

        self.left_panel = Label(text="Text Input/Output placeholder", size_hint=(0.4, 1))
        self.add_widget(self.left_panel)
        self.text_input = TextInput(multiline=False)
        self.left_panel.add_widget(self.text_input)
        self.text_input.bind(text=self.on_text)

        self.right_panel = BoxLayout(orientation='vertical', size_hint=(0.6, 1))
        self.map_screen = MapScreen()
        self.render_button = Button(text="Render Map", size_hint=(1, 0.1))
        self.render_button.bind(on_press=self.on_render_map)

        self.right_panel.add_widget(self.render_button)
        map_container = FloatLayout(size_hint=(1, 0.9))
        # with map_container.canvas.before:
        #     Color(0.9, 1, 0.8, 0.5)  # Light green, semi-transparent
        #     self.map_bg = Rectangle(pos=map_container.pos, size=map_container.size)
        # map_container.bind(pos=lambda w, v: setattr(self.map_bg, 'pos', v),
        #                    size=lambda w, v: setattr(self.map_bg, 'size', v))
        self.map_screen.size_hint = (0.8, 0.8)
        self.map_screen.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        map_container.add_widget(self.map_screen)
        self.right_panel.add_widget(map_container)
        self.add_widget(self.right_panel)

    def on_render_map(self, instance):
        self.map_screen.draw_map()

    def on_text(self, instance, value):
        print('The widget', instance, 'have:', value)

class SankharaApp(App):
    def build(self):
        Window.size = (1024, 600)
        return MainScreen()

if __name__ == '__main__':
    SankharaApp().run()
