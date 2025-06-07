from entities.player_state import PlayerState
from entities.lineage import Family
from typing import Optional

class Player:
    def __init__(self, player_id: str, family: 'Family', state: PlayerState, karma: float = 0.0):
        self.player_id = player_id  # Unique identifier
        self.family = family        # Reference to Family object
        self.state = state          # PlayerState instance
        self.karma = karma          # Karma score (float)

    def reincarnate(self, new_state: PlayerState, new_family: Optional['Family'] = None):
        """Reincarnate the player with a new state and optionally a new family."""
        self.state = new_state
        if new_family:
            self.family = new_family

    # Additional methods for gameplay, interaction, etc. can be added here

