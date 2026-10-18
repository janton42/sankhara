"""Roles among the people. Every role gets the same number of attention slots; what
differs is the kind and reach of what they can do. A few roles exist from the start;
others appear only once the people have found a way of life that needs them, and
some grow rarer as that happens.
"""

from dataclasses import dataclass, field

ACTION_SLOTS = 3
ADULT_AGE = 16


@dataclass(frozen=True)
class Station:
    id: str
    title: str  # shown to the player
    rebirth_weight: float  # relative chance of being born into this role
    land: str  # what their food depends on: "plant", "animal", "water" or "mixed"
    income: dict  # yearly, before the land's richness; categories the people lack are ignored
    hands: float  # the family's labour each year
    start: dict  # means on coming of age
    requires: str | None = None  # a discovery the role needs
    requires_forms: tuple = ()  # ...and, if given, one of these forms of it
    fades_with: str | None = None  # a discovery after which fewer people live this way
    leads: bool = False
    domains: tuple = field(default=())  # kinds of discovery they can work at


STATIONS = {
    s.id: s
    for s in [
        Station(
            "leader",
            "Leader",
            4,
            "mixed",
            income={"food": 6, "regard": 3},
            hands=5,
            start={"food": 12, "regard": 15},
            leads=True,
            domains=("land", "craft", "lore", "kin"),
        ),
        Station(
            "keeper",
            "Keeper of the songs",
            10,
            "mixed",
            income={"food": 4, "regard": 2.5},
            hands=4,
            start={"food": 8, "regard": 8},
            domains=("lore", "kin"),
        ),
        Station(
            "hunter",
            "Hunter",
            25,
            "animal",
            income={"food": 8, "regard": 1},
            hands=5,
            start={"food": 10, "regard": 3},
            fades_with="herding",
            domains=("land", "craft"),
        ),
        Station(
            "gatherer",
            "Gatherer",
            30,
            "plant",
            income={"food": 8, "regard": 1},
            hands=5,
            start={"food": 10, "regard": 3},
            fades_with="cultivation",
            domains=("land", "lore"),
        ),
        Station(
            "maker",
            "Maker",
            14,
            "mixed",
            income={"food": 5, "regard": 1.5},
            hands=5,
            start={"food": 8, "regard": 4},
            domains=("craft",),
        ),
        Station(
            "fisher",
            "Fisher",
            14,
            "water",
            income={"food": 9, "regard": 1},
            hands=5,
            start={"food": 10, "regard": 3},
            requires="fishing",
            domains=("land", "craft"),
        ),
        Station(
            "planter",
            "Planter",
            34,
            "plant",
            income={"food": 11, "regard": 1},
            hands=6,
            start={"food": 12, "regard": 3},
            requires="cultivation",
            domains=("land",),
        ),
        Station(
            "herder",
            "Herder",
            18,
            "animal",
            income={"food": 9, "regard": 1},
            hands=5,
            start={"food": 12, "regard": 3},
            requires="herding",
            domains=("land",),
        ),
        Station(
            "warrior",
            "One who fights",
            10,
            "animal",
            income={"food": 5, "regard": 2},
            hands=5,
            start={"food": 8, "regard": 5},
            requires="warriors",
            requires_forms=("war_band",),
            domains=("craft", "kin"),
        ),
        Station(
            "trader",
            "Go-between",
            8,
            "mixed",
            income={"food": 4, "regard": 2, "wares": 3, "tokens": 3},
            hands=4,
            start={"food": 8, "regard": 5, "wares": 4, "tokens": 4},
            requires="exchange",
            requires_forms=("barter", "tokens"),
            domains=("kin", "craft"),
        ),
    ]
}

BAND_ROLES = ("keeper", "hunter", "gatherer", "maker")  # the first roles a child can take


def is_open(station, nation):
    """Whether this role exists among the people yet."""
    if station.requires is None:
        return True
    form = nation.known.get(station.requires)
    if form is None:
        return False
    return not station.requires_forms or form in station.requires_forms


def open_stations(nation):
    return [s for s in STATIONS.values() if is_open(s, nation)]


def rebirth_weights(nation):
    """How likely each role is at birth, given how the people live now."""
    out = {}
    for s in open_stations(nation):
        weight = s.rebirth_weight
        if s.fades_with and s.fades_with in nation.known:
            weight *= 0.35
        out[s.id] = weight
    return out


def station_title(char, nation):
    """Titles can change as the people's ways change (a council's first elder, a chief...)."""
    return nation.names.get(f"title:{char.station}", STATIONS[char.station].title)
