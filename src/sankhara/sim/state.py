"""Game state: plain dataclasses that serialise to and from JSON-friendly dicts.

Everything the simulation needs lives here so a game can be saved and resumed
exactly. Rules live in the sibling modules; this file only holds data.
"""

import random
from dataclasses import asdict, dataclass, field, fields

# What every budget starts with. Discoveries can add more (whatever the people come to
# use for exchange), so budgets are open-ended.
BASE_CATEGORIES = ("food", "hands", "regard")


@dataclass
class Budget:
    """A pool of coarse means: the people's common stores, or a family's."""

    amounts: dict[str, float] = field(default_factory=dict)

    def get(self, category):
        return self.amounts.get(category, 0.0)

    def set(self, category, value):
        self.amounts[category] = value

    def can_afford(self, cost):
        return all(self.get(c) >= amount - 1e-9 for c, amount in cost.items())

    def add(self, amounts, scale=1.0):
        for c, amount in amounts.items():
            self.amounts[c] = self.get(c) + amount * scale

    def spend(self, cost):
        self.add(cost, -1.0)

    def clamp_nonnegative(self):
        for c in self.amounts:
            self.amounts[c] = max(0.0, self.amounts[c])

    def copy(self):
        return Budget(dict(self.amounts))


@dataclass
class Character:
    id: int
    name: str
    family_name: str
    gender: str
    birth_year: int
    death_age: int  # hidden; the player never sees it
    station: str  # their role among the people
    settlement_id: int
    health: float = 80.0
    alive: bool = True
    death_year: int | None = None
    cause_of_death: str = ""
    mother_id: int | None = None
    father_id: int | None = None
    spouse_id: int | None = None
    children: list[int] = field(default_factory=list)
    means: Budget = field(default_factory=Budget)
    tendencies: dict[str, float] = field(default_factory=dict)  # hidden
    karma: float = 0.0  # hidden; used for NPCs, the player's lives on the Soul
    affinity: dict[str, float] = field(default_factory=dict)  # other id (str) -> -1..1
    family_stability: float = 1.0  # multiplier on family misfortune
    fortune: float = 1.0  # multiplier on what the family brings in
    origin: str = ""  # the people they were born among, if not ours
    is_player: bool = False
    is_elder: bool = False
    former_station: str = ""  # what a leader did before the people turned to them

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
    """A camp of the people (later perhaps a village or more)."""

    id: int
    name: str
    col: int
    row: int
    population: float
    is_seat: bool = False  # where the leader lives
    kind: str = "camp"
    works: dict[str, int] = field(default_factory=dict)  # gathering place, store pits, fields...
    cohesion: float = 55.0
    plenty: float = 45.0
    food_balance: float = 0.0  # last year's surplus (+) or shortfall (-)


@dataclass
class Nation:
    """The people as a whole."""

    name: str
    culture: str  # elevation band whose naming culture the people share
    stores: Budget  # what is held in common
    territory: list[list[int]]  # [col, row] pairs: the land the people range over
    leader_id: int | None = None
    leading_family: str = ""
    cohesion: float = 55.0
    plenty: float = 45.0
    lore: float = 15.0  # songs, stories and remembered skill
    known: dict[str, str] = field(default_factory=dict)  # discovery id -> chosen form ("" if none)
    insight: dict[str, float] = field(default_factory=dict)  # discovery id -> progress
    succession: str = "respected"  # how a new leader is found
    names: dict[str, str] = field(default_factory=dict)  # display names: categories, titles


@dataclass
class Neighbour:
    """Another people on the map, simulated coarsely."""

    id: int
    name: str
    culture: str
    col: int
    row: int
    territory: list[list[int]]
    population: float
    temper: float  # 0 peaceable .. 1 quick to violence
    relations: float = 0.0  # -1 hostile .. 1 close
    met: bool = False
    known: list[str] = field(default_factory=list)


@dataclass
class Project:
    """Something that takes years of attention. The people's works (`common`) outlive
    whoever leads them: others can help, take them up, or call more people to them."""

    id: int
    kind: str
    leader_id: int | None  # None: left unfinished, waiting for someone to take it up
    needed: float  # work to finish, in years of one person's attention
    done: float = 0.0
    target: str | None = None
    common: bool = False
    helpers: list[int] = field(default_factory=list)
    support: float = 0.0  # help from people at large, raised by calling on them
    started: int = 0
    started_by: str = ""
    worked_by: list[str] = field(default_factory=list)  # the player's characters who worked it
    rate: float = 1.0  # work done last year, for estimates
    stalled: bool = False


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
    answers: list[str] = field(default_factory=list)  # ways the player could meet it
    expected: bool = False  # something is expected of the player: ignoring it weighs
    penalty: float = 0.0  # karma cost of ignoring it when expected
    data: dict = field(default_factory=dict)

    @property
    def key(self):
        """Stable across years, so an answer can be kept up while the matter lasts."""
        return f"{self.kind}:{self.settlement_id or ''}:{self.target_id or ''}"


@dataclass
class GameState:
    seed: int
    year: int
    nation: Nation
    soul: Soul
    player_id: int
    characters: dict[str, Character] = field(default_factory=dict)  # id (str) -> Character
    settlements: dict[str, Settlement] = field(default_factory=dict)
    neighbours: dict[str, Neighbour] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)
    events: list[EventInstance] = field(default_factory=list)  # this year's
    plan: list[str | None] = field(default_factory=list)  # chosen option keys per slot
    modifiers: dict[str, float] = field(default_factory=dict)  # this year's world effects
    pending_choice: str | None = None  # a discovery whose form is being settled
    pending_mode: str = ""  # "decide" (the player chooses) or "voice" (the player speaks for one)
    commitments: dict[str, int] = field(default_factory=dict)  # player's project id -> slot
    legacy: list[dict] = field(default_factory=list)  # what the player's lives set in motion
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

    def neighbour(self, nid):
        return self.neighbours.get(str(nid)) if nid is not None else None

    @property
    def leader(self):
        return self.character(self.nation.leader_id)

    @property
    def seat(self):
        return next(s for s in self.settlements.values() if s.is_seat)

    def living(self):
        return [c for c in self.characters.values() if c.alive]

    def new_id(self):
        nid = self.next_id
        self.next_id += 1
        return nid

    def add_character(self, char):
        self.characters[str(char.id)] = char
        return char

    def projects_of(self, cid):
        """Projects this character leads."""
        return [p for p in self.projects.values() if p.leader_id == cid]

    def helping(self, cid):
        """The people's works this character is helping with."""
        return [p for p in self.projects.values() if cid in p.helpers]

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
        nation["stores"] = Budget(**nation["stores"])
        data["nation"] = _known(Nation, nation)
        data["soul"] = _known(Soul, data["soul"])
        data["characters"] = {k: _character(v) for k, v in data["characters"].items()}
        data["settlements"] = {k: _known(Settlement, v) for k, v in data["settlements"].items()}
        data["neighbours"] = {k: _known(Neighbour, v) for k, v in data["neighbours"].items()}
        data["projects"] = {k: _known(Project, v) for k, v in data["projects"].items()}
        data["events"] = [_known(EventInstance, e) for e in data["events"]]
        return _known(cls, data)


def _known(cls, data):
    """Build a dataclass, ignoring keys it doesn't (or no longer) have."""
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


def _character(data):
    data = dict(data)
    data["means"] = Budget(**data["means"])
    return _known(Character, data)
