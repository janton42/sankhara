"""The people's yearly round: food from the land, hunger and growth, what goes into the
common stores, and the slow drift of cohesion, plenty and lore. Camps are simulated as
population figures; the families of tracked characters keep their own means.
"""

import math

from sankhara.sim import discoveries
from sankhara.sim.stations import ADULT_AGE, STATIONS
from sankhara.sim.world import camp_tiles, forage_value, is_watery, resource

FOOD_NEED = 0.1  # food per person per year
FOOD_YIELD = 0.1  # food per person per year when a camp is at half its capacity
CAP_PER_TILE = 40  # people a tile can feed by foraging at forage value 1.0
SHARE_OF_SURPLUS = 0.3  # how much of a good year's surplus goes to the common stores
STORES_SPOILAGE = 0.35  # how much of the common stores rots each year, before food keeping
MIN_SPOILAGE = 0.05
HANDS_BASE = 25  # labour the people can spare in common each year, at 250 people
WORK_CAPS = {
    "gathering": 1,
    "pits": 2,
    "fields": 3,
    "weir": 2,
    "herd": 3,
    "sacred": 1,
    "paths": 1,
}
GROWTH = 0.02
TOWN_SIZE = 600  # a village this big becomes a town, once the people know what that is
KINDS = ("camp", "village", "town")


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def adjust_settlements(state, *, cohesion=0.0, plenty=0.0, only=None):
    """Nudge cohesion/plenty across the people (or one camp)."""
    targets = [state.settlement(only)] if only is not None else state.settlements.values()
    for s in targets:
        s.cohesion = clamp(s.cohesion + cohesion)
        s.plenty = clamp(s.plenty + plenty)
    refresh_averages(state)


def advance(nation, field, amount):
    """Raise lore with diminishing returns as it approaches 100."""
    value = getattr(nation, field)
    setattr(nation, field, clamp(value + amount * (1 - value / 100)))


def refresh_averages(state):
    nation = state.nation
    total = state.total_population() or 1
    nation.cohesion = sum(s.cohesion * s.population for s in state.settlements.values()) / total
    nation.plenty = sum(s.plenty * s.population for s in state.settlements.values()) / total


def people_scale(state):
    """Common undertakings cost (and give) more as the people grow."""
    return max(1.0, (state.total_population() / 250) ** 0.5)


def capacity(state, settlement, fx=None):
    """How many people a camp's land can feed in an ordinary year."""
    fx = fx if fx is not None else discoveries.effects(state)
    fishing = fx.get("fishing", False)
    land = sum(forage_value(t, fishing) for t in camp_tiles(state, settlement))
    works = settlement.works
    bonus = 1 + 0.15 * works.get("fields", 0) + 0.1 * works.get("herd", 0)
    bonus += 0.12 * works.get("weir", 0)
    return max(30.0, CAP_PER_TILE * land * fx.get("capacity_mult", 1.0) * bonus)


def hands_available(state):
    """What the people can give to common work this year."""
    nation = state.nation
    return round(HANDS_BASE * people_scale(state) * (0.6 + 0.4 * nation.cohesion / 55))


def economy_year(state):
    """Run one year of the people's life on the land. Returns lines about notable outcomes."""
    nation = state.nation
    fx = discoveries.effects(state)
    mods = state.modifiers
    notes = []
    relief = mods.get("relief", 0.0)
    hungry = []
    share = min(0.8, SHARE_OF_SURPLUS + fx.get("stores_share", 0))
    scale = people_scale(state)
    # the more people, the harder it is to hold them together
    size_strain = 6 * math.log2(max(1.0, state.total_population() / 300))
    paths = (
        3 if state.seat.works.get("paths") else 0
    )  # camps that can reach each other hold together

    for s in state.settlements.values():
        if fx.get("settled") and s.kind == "camp":
            s.kind = "village"
        if fx.get("towns") and s.kind == "village" and s.population >= TOWN_SIZE:
            s.kind = "town"
        cap = capacity(state, s, fx)
        ratio = s.population / cap
        season = mods.get("harvest", 1.0) * mods.get(f"harvest:{s.id}", 1.0)
        production = (
            s.population * FOOD_YIELD * (1.3 - 0.6 * ratio) * fx.get("food_mult", 1.0) * season
        )
        need = s.population * FOOD_NEED
        surplus = production - need
        # what reaches the common stores grows with the people as what is drawn from them
        # does (people_scale), not with every mouth: distant camps keep more of their own
        given = max(0.0, surplus) * share / scale
        balance = surplus - given
        if balance < 0:
            # store pits soften a lean year
            balance += min(-balance, need * 0.05 * s.works.get("pits", 0))
        if balance < 0 and relief > 0:
            used = min(relief, -balance)
            relief -= used
            balance += used
        s.food_balance = balance
        nation.stores.add({"food": given})

        if balance < 0:
            hunger = min(1.0, -balance / need)
            s.population *= 1 - 0.3 * hunger
            s.cohesion = clamp(s.cohesion - 15 * hunger)
            s.plenty = clamp(s.plenty - 8 * hunger)
            hungry.append(s.name)
        else:
            rate = GROWTH * (1 + 0.5 * (s.plenty - 50) / 50) * (1.15 if fx.get("settled") else 1)
            s.population += s.population * rate * (1 - ratio)

        plague = mods.get("plague", 0.0) * fx.get("plague_mult", 1.0)
        if plague:
            s.population *= 1 - plague
        s.population = max(12.0, s.population)

        surplus_ratio = max(-0.5, min(0.5, balance / need))
        crowding = max(0.0, ratio - 0.9) * 40
        target_cohesion = (
            52
            + fx.get("cohesion", 0)
            + 6 * s.works.get("gathering", 0)
            + 4 * s.works.get("sacred", 0)
            + paths
            + (s.plenty - 45) * 0.15
            + nation.lore / 20
            - crowding
            - size_strain
        )
        s.cohesion = clamp(s.cohesion + 0.15 * (target_cohesion - s.cohesion))
        target_plenty = 45 + 25 * surplus_ratio + fx.get("plenty", 0) + paths
        s.plenty = clamp(s.plenty + 0.15 * (target_plenty - s.plenty))

    if hungry:
        notes.append(f"Hunger in {', '.join(hungry)}.")

    spoilage = max(MIN_SPOILAGE, STORES_SPOILAGE + fx.get("spoilage", 0))
    nation.stores.set("food", nation.stores.get("food") * (1 - spoilage))
    for category in ("wares", "tokens", "favours"):
        if category in nation.stores.amounts:
            nation.stores.set(category, nation.stores.get(category) * 0.97)
    nation.stores.set("hands", hands_available(state))
    nation.stores.clamp_nonnegative()

    # what the people remember fades unless it is sung
    nation.lore *= 0.98
    advance(nation, "lore", 0.4 + fx.get("lore", 0))

    refresh_averages(state)
    return notes


# --- families ---------------------------------------------------------------

FAMILY_SPOILAGE = 0.3
DEPENDANT_FOOD = 1.5  # per young child
ADULT_FOOD = 3.0
REGARD_FADE = 0.06


def dependants(state, char):
    """Young children eat from their father's family (or their mother's, if he is gone)."""
    if char.gender == "female" and state.character(char.spouse_id):
        return 0
    return sum(
        1
        for cid in char.children
        if (c := state.character(cid)) and c.alive and c.age(state.year) < ADULT_AGE
    )


def land_richness(state, settlement, land):
    tiles = camp_tiles(state, settlement)
    if not tiles:
        return 1.0
    fish = discoveries.fx(state, "fishing")
    if land == "plant":
        value = sum(resource(t, "plant_food") for t in tiles)
    elif land == "animal":
        value = sum(resource(t, "animal_food") for t in tiles)
    elif land == "water":
        value = sum(1.0 if is_watery(t) else 0.3 for t in tiles) if fish else 0.3 * len(tiles)
    else:
        value = sum(forage_value(t) for t in tiles)
    return 0.6 + 0.6 * value / len(tiles)


def households_year(state):
    """What each tracked adult's family brings in and uses up. Returns notes for the player."""
    notes = []
    nation = state.nation
    fx = discoveries.effects(state)
    in_use = set(discoveries.categories(nation))
    for char in state.living():
        if char.age(state.year) < ADULT_AGE:
            continue
        station = STATIONS[char.station]
        settlement = state.settlement(char.settlement_id) or state.seat
        season = state.modifiers.get("harvest", 1.0)
        income = {c: v for c, v in station.income.items() if c in in_use}
        income["food"] = (
            income.get("food", 0)
            * land_richness(state, settlement, station.land)
            * season
            * fx.get("food_mult", 1.0)
        )
        if station.leads:
            income["regard"] = income.get("regard", 0) + fx.get("leader_regard", 0)
            # what the people give the one who leads them, if that is their custom
            income["food"] += fx.get("leader_food", 0) * people_scale(state)
        char.means.add(income, char.fortune)
        char.means.add({"food": ADULT_FOOD + DEPENDANT_FOOD * dependants(state, char)}, -1)
        spoil = max(MIN_SPOILAGE, FAMILY_SPOILAGE + fx.get("spoilage", 0))
        char.means.set("food", char.means.get("food") * (1 - spoil))
        char.means.set("regard", char.means.get("regard") * (1 - REGARD_FADE))
        char.means.set("hands", station.hands * (0.5 + char.health / 200))
        if char.means.get("food") < 0:
            # a band shares: a hungry family is fed from the common stores if it can be
            short = -char.means.get("food")
            taken = min(short, nation.stores.get("food"))
            nation.stores.add({"food": -taken})
            char.means.add({"food": taken})
        if char.means.get("food") < 0:
            char.health -= 8
            if char.is_player:
                notes.append("Your family went hungry.")
        char.means.clamp_nonnegative()
    return notes
