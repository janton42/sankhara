"""Social stations. Every station gets the same number of action slots; what differs is
the kind and reach of the actions and which budget they draw on."""

from dataclasses import dataclass

ACTION_SLOTS = 3
ADULT_AGE = 16


@dataclass(frozen=True)
class Station:
    id: str
    title: str  # shown to the player
    household_title: str  # what their budget is called
    rebirth_weight: float  # chance of being born into this station
    income: dict  # household income per year, before fertility and fortune
    upkeep: dict  # household costs per year
    start: dict  # household means on coming of age


STATIONS = {
    s.id: s
    for s in [
        Station(
            "ruler",
            "Ruler",
            "Treasury",
            7,
            income={"food": 10, "coin": 10, "goods": 4},
            upkeep={"food": 6, "coin": 4},
            start={"food": 30, "coin": 30, "goods": 10},
        ),
        Station(
            "noble",
            "Noble",
            "Estate",
            13,
            income={"food": 10, "coin": 9, "goods": 3},
            upkeep={"food": 6, "coin": 4},
            start={"food": 25, "coin": 25, "goods": 8},
        ),
        Station(
            "scholar",
            "Scholar",
            "Means",
            13,
            income={"food": 6, "coin": 4, "goods": 1},
            upkeep={"food": 5, "coin": 1},
            start={"food": 10, "coin": 8, "goods": 3},
        ),
        Station(
            "merchant",
            "Merchant",
            "Purse",
            15,
            income={"food": 5, "coin": 8, "goods": 4},
            upkeep={"food": 5, "coin": 2},
            start={"food": 10, "coin": 20, "goods": 10},
        ),
        Station(
            "artisan",
            "Artisan",
            "Workshop",
            20,
            income={"food": 5, "coin": 4, "goods": 5},
            upkeep={"food": 5, "coin": 1},
            start={"food": 10, "coin": 8, "goods": 8},
        ),
        Station(
            "farmer",
            "Farmer",
            "Household",
            32,
            income={"food": 10, "coin": 2, "goods": 1},
            upkeep={"food": 6, "coin": 1},
            start={"food": 15, "coin": 4, "goods": 3},
        ),
    ]
}


def station_title(char, nation):
    """Ruling-house children who aren't the ruler are shown as royals, not plain nobles."""
    if char.station == "noble" and char.family_name == nation.dynasty:
        return "Royal"
    return STATIONS[char.station].title
