from kivy.app import App
from kivy.uix.widget import Widget

class RootWidget(Widget):
    pass

class SankharaApp(App):
    def build(self):
        return RootWidget()

if __name__ == "__main__":
    SankharaApp().run()