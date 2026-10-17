from typing import Any


class PlayerState:
    def __init__(
        self,
        species: str = "human",
        age: int = 0,
        health: float = 100.0,
        happiness: float = 50.0,
        attributes: dict[str, Any] = None,
    ):
        self.species = species  # 'human', 'wolf', '
        self.age = age
        self.health = health
        self.happiness = happiness

    def is_alive(self) -> bool:
        return self.health > 0
