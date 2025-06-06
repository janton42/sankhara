from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.dropdown import DropDown
from entities.player import Player
from entities.player_state import PlayerState
from entities.lineage import Family
from ui.screens.info_panel import format_tile_info
from constants.config import ACTIONS

class InfoPanel(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.player = None
        self.spacing = 10
        self.padding = [10, 10, 10, 10]
        # Add a top spacer to push content down ~1/4 of the way
        self.top_spacer = BoxLayout(size_hint_y=0.25)
        self.add_widget(self.top_spacer)
        self.turn = 0
        self.turn_label = Label(text=f"Turn: {self.turn}", size_hint_y=None, height=30)
        self.add_widget(self.turn_label, index=1)  # Add just below the top spacer
        self.player_label = Label(text="Player: Not started", size_hint_y=None, height=80)
        self.start_button = Button(text="Start Game", size_hint_y=None, height=40)
        self.start_button.bind(on_press=self.on_start_game)
        # Action dropdowns
        self.action_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=60, spacing=0)
        self.action_dropdowns = []
        self.selected_actions = [None, None, None, None]
        self.choice_labels = []
        for i in range(4):
            vbox = BoxLayout(orientation='vertical', size_hint_x=1, spacing=0)
            dropdown = DropDown()
            main_button = Button(text=f"Action {i+1}", size_hint_y=None, height=35, disabled=True)
            self.populate_dropdown(dropdown, main_button, i)
            main_button.bind(on_release=dropdown.open)
            vbox.add_widget(main_button)
            label = Label(text="", size_hint_y=None, height=20)
            vbox.add_widget(label)
            self.action_box.add_widget(vbox)
            self.action_dropdowns.append((main_button, dropdown, label))
        self.tile_label = Label(text="No tile selected.")
        self.add_widget(self.player_label)
        self.add_widget(self.start_button)
        self.add_widget(self.action_box)
        self.add_widget(self.tile_label)

    def populate_dropdown(self, dropdown, main_button, idx):
        dropdown.clear_widgets()
        used_ids = set(a['id'] for a in self.selected_actions if a)
        for action in ACTIONS:
            if not action['repeatable'] and action['id'] in used_ids:
                continue
            btn = Button(text=f"{action['name']} ({action['hours']}h)", size_hint_y=None, height=35)
            btn.action_data = action
            btn.bind(on_release=lambda btn, mb=main_button, dd=dropdown, i=idx: self.select_action(btn, mb, dd, i))
            dropdown.add_widget(btn)

    def on_start_game(self, instance):
        family = Family(family_id="fam1")
        state = PlayerState()
        self.player = Player(player_id="p1", family=family, state=state)
        self.player_label.text = self.format_player_info()
        self.start_button.text = "Take Action"
        self.start_button.unbind(on_press=self.on_start_game)
        self.start_button.bind(on_press=self.on_take_action)
        # Enable action dropdowns
        for i, (main_button, _, _) in enumerate(self.action_dropdowns):
            main_button.disabled = False
            self.selected_actions[i] = None
            self.populate_dropdown(self.action_dropdowns[i][1], main_button, i)

    def select_action(self, btn, main_button, dropdown, idx):
        action = btn.action_data
        self.selected_actions[idx] = action
        main_button.text = btn.text
        dropdown.dismiss()
        self.update_dropdown_states()

    def update_dropdown_states(self):
        total_hours = sum(a['hours'] for a in self.selected_actions if a)
        for i, (main_button, dropdown, _) in enumerate(self.action_dropdowns):
            if self.selected_actions[i]:
                continue
            # Only show actions that fit in the remaining hours
            remaining = 24 - total_hours
            self.populate_dropdown(dropdown, main_button, i)
            # Disable if no actions fit
            has_valid = any(action['hours'] <= remaining for action in ACTIONS if (action['repeatable'] or action['id'] not in [a['id'] for a in self.selected_actions if a]))
            main_button.disabled = not has_valid or remaining <= 0
        # If any selected action puts us over 24, disable all others
        if total_hours > 24:
            for i, (main_button, _, _) in enumerate(self.action_dropdowns):
                if not self.selected_actions[i]:
                    main_button.disabled = True

    def on_take_action(self, instance):
        self.turn += 1
        self.turn_label.text = f"Turn: {self.turn}"
        # Print the selected choices under their respective button, then reset buttons
        for i, (main_button, dropdown, label) in enumerate(self.action_dropdowns):
            label.text = main_button.text
            main_button.text = f"Action {i+1}"
            main_button.disabled = False
            self.selected_actions[i] = None
            self.populate_dropdown(dropdown, main_button, i)
        self.update_dropdown_states()

    def format_player_info(self):
        if not self.player:
            return "Player: Not started"
        s = self.player.state
        return (f"Player\n"
                f"Species: {s.species}          Age: {s.age}\n"
                f"Health: {s.health}            Happiness: {s.happiness}\n"
                f"Family: {self.player.family.name}     Karma: {self.player.karma}\n"
                )

    def update_tile_info(self, tile):
        self.tile_label.text = format_tile_info(tile)

