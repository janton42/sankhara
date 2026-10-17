from typing import Optional

from sankhara.core.game_engine import coin_flip
from sankhara.entities.lineage import Family
from sankhara.entities.player_state import PlayerState

from .namer import make_name


class Player:
    def __init__(self, player_id: str, family: "Family", state: PlayerState, karma: float = 0.0):
        self.player_id = player_id  # Unique identifier
        self.family = family  # Reference to Family object
        self.state = state  # PlayerState instance
        self.karma = karma  # Karma score (float)
        self.gender = ""
        self.name = ""

    def set_player_gender(self):
        genders = ["male", "female"]
        self.gender = genders[coin_flip()]

    def set_player_name(self):
        first_name = make_name(self.family.home["biome"].split(" ")[0], self.gender).split(" ")[0]
        last_name = self.family.name
        self.name = f"{first_name} {last_name}"

    def reincarnate(self, new_state: PlayerState, new_family: Optional["Family"] = None):
        """Reincarnate the player with a new state and optionally a new family."""
        self.state = new_state
        if new_family:
            self.family = new_family

    # Additional methods for gameplay, interaction, etc. can be added here
