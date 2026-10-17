"""Game state: plain dataclasses that serialise to and from JSON-friendly dicts.

Everything the simulation needs lives here so a game can be saved and resumed
exactly. Rules live in the sibling modules; this file only holds data.
"""

import random
from dataclasses import asdict, dataclass, field, fields

CATEGORIES = ("food", "goods", "coin")


@dataclass
class Budget:
    """A pool of the coarse resource categories: the nation's treasury or a household's means."""

    food: float = 0.0
    goods: float = 0.0
    coin: float = 0.0

    def get(self, category):
        return getattr(self, category)

    def can_afford(self, cost):
        return all(self.get(c) >= amount for c, amount in cost.items())

    def add(self, amounts, scale=1.0):
        for c, amount in amounts.items():
            setattr(self, c, getattr(self, c) + amount * scale)

    def spend(self, cost):
        self.add(cost, -1.0)

    def clamp_nonnegative(self):
        for c in CATEGORIES:
            setattr(self, c, max(0.0, getattr(self, c)))


@dataclass
class Character:
    id: int
    name: str
    family_name: str
    gender: str
    birth_year: int
    death_age: int  # hidden; the player never sees it
    station: str
    settlement_id: int
    health: float = 80.0
    alive: bool = True
    death_year: int | None = None
    cause_of_death: str = ""
    mother_id: int | None = None
    father_id: int | None = None
    spouse_id: int | None = None
    children: list[int] = field(default_factory=list)
    household: Budget = field(default_factory=Budget)
    tendencies: dict[str, float] = field(default_factory=dict)  # hidden
    karma: float = 0.0  # hidden; used for NPCs, the player's lives on the Soul
    affinity: dict[str, float] = field(default_factory=dict)  # other id (str) -> -1..1
    family_stability: float = 1.0  # multiplier on family misfortune
    fortune: float = 1.0  # multiplier on household income
    is_player: bool = False
    is_advisor: bool = False

    def age(self, year):
        return year - self.birth_year

    @property
    def full_name(self):
        return f"{self.name} {self.family_name}"

    def feels(self, other_id):
        return self.affinity.get(str(other_id), 0.0)

    def adjust_affinity(self, other_id, delta):
        key = str(other_id)
        self.affinity[key] = max(-1.0, min(1.0, self.affinity.get(key, 0.0) + delta))


@dataclass
class Settlement:
    id: int
    name: str
    col: int
    row: int
    population: float
    is_capital: bool = False
    works: dict[str, int] = field(default_factory=dict)  # irrigation, granary, school, roads...
    stability: float = 55.0
    prosperity: float = 45.0
    food_balance: float = 0.0  # last year's surplus (+) or shortfall (-)


@dataclass
class Nation:
    name: str
    culture: str  # elevation band whose naming culture the people share
    dynasty: str
    treasury: Budget
    territory: list[list[int]]  # [col, row] pairs
    ruler_id: int | None = None
    tax_rate: float = 0.15
    stability: float = 55.0
    prosperity: float = 45.0
    learning: float = 5.0
    arts: float = 5.0


@dataclass
class Soul:
    """What carries from one life to the next. Hidden from the player."""

    karma: float = 0.0
    tendencies: dict[str, float] = field(default_factory=dict)
    lives: list[dict] = field(default_factory=list)  # summaries of finished lives


@dataclass
class EventInstance:
    kind: str
    text: str
    settlement_id: int | None = None
    target_id: int | None = None
    obligation: str | None = None  # action id expected of the player this year
    penalty: float = 0.0  # karma cost of ignoring the obligation
    data: dict = field(default_factory=dict)


@dataclass
class GameState:
    seed: int
    year: int
    nation: Nation
    soul: Soul
    player_id: int
    characters: dict[str, Character] = field(default_factory=dict)  # id (str) -> Character
    settlements: dict[str, Settlement] = field(default_factory=dict)
    events: list[EventInstance] = field(default_factory=list)  # this year's
    plan: list[str | None] = field(default_factory=list)  # chosen action ids per slot
    defaults: list[str] = field(default_factory=list)  # what habit suggested this year
    modifiers: dict[str, float] = field(default_factory=dict)  # this year's world effects
    log: list[str] = field(default_factory=list)
    next_id: int = 1
    rng_state: list | None = None
    life_over: bool = False

    # --- lookups -----------------------------------------------------------

    @property
    def player(self):
        return self.characters[str(self.player_id)]

    def character(self, cid):
        return self.characters.get(str(cid)) if cid is not None else None

    def settlement(self, sid):
        return self.settlements.get(str(sid)) if sid is not None else None

    @property
    def ruler(self):
        return self.character(self.nation.ruler_id)

    def living(self):
        return [c for c in self.characters.values() if c.alive]

    def new_id(self):
        nid = self.next_id
        self.next_id += 1
        return nid

    def add_character(self, char):
        self.characters[str(char.id)] = char
        return char

    def total_population(self):
        return sum(s.population for s in self.settlements.values())

    # --- randomness ----------------------------------------------------------

    def rng(self):
        """The game's RNG, restored from saved state so reloads replay identically."""
        if not hasattr(self, "_rng"):
            self._rng = random.Random(self.seed)
            if self.rng_state is not None:
                version, internal, gauss = self.rng_state
                self._rng.setstate((version, tuple(internal), gauss))
        return self._rng

    # --- serialisation -------------------------------------------------------

    def to_dict(self):
        if hasattr(self, "_rng"):
            version, internal, gauss = self._rng.getstate()
            self.rng_state = [version, list(internal), gauss]
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        nation = dict(data["nation"])
        nation["treasury"] = Budget(**nation["treasury"])
        data["nation"] = Nation(**nation)
        data["soul"] = Soul(**data["soul"])
        data["characters"] = {k: _character(v) for k, v in data["characters"].items()}
        data["settlements"] = {k: Settlement(**v) for k, v in data["settlements"].items()}
        data["events"] = [EventInstance(**e) for e in data["events"]]
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def _character(data):
    data = dict(data)
    data["household"] = Budget(**data["household"])
    return Character(**data)
