from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.window import Window

class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.add_widget(Label(text="Text Input/Output placeholder", size_hint=(0.4, 1)))
        self.add_widget(Label(text="Map placeholder", size_hint=(0.6, 1)))

class SankharaApp(App):
    def build(self):
        Window.size = (1024, 600)
        return MainScreen()

if __name__ == '__main__':
    SankharaApp().run()
