"""The nation's yearly economy: harvests, hunger and growth, taxes, upkeep, and the slow
drift of stability, prosperity, learning and the arts. Settlements are simulated as
population figures; households of tracked characters earn and spend separately."""

from sankhara.sim.stations import ADULT_AGE, STATIONS
from sankhara.sim.world import settlement_fertility

FOOD_NEED = 0.1  # food per person per year
FOOD_YIELD = 0.105  # food per person per year at fertility 1.0
TAX_FOOD_SHARE = 0.4  # share of the tax rate taken from the harvest
COIN_PER_PERSON = 0.03
GOODS_PER_PERSON = 0.012
BASE_TAX = 0.15
COURT_UPKEEP = {"coin": 15, "goods": 5}
UPKEEP_PER_PERSON = {"coin": 0.012, "goods": 0.002}  # administration grows with the realm
SPOILAGE = {"food": 0.1, "goods": 0.03, "coin": 0.03}  # stores rot, coffers leak
WORK_CAPS = {"irrigation": 4, "granary": 3, "school": 2, "shrine": 2, "roads": 3}
CAPACITY_PER_FERTILITY = 1500
GRANARY_COVER = 0.06  # share of need a granary level covers in a bad year


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def adjust_settlements(state, *, stability=0.0, prosperity=0.0, only=None):
    """Nudge stability/prosperity across the realm (or one settlement)."""
    targets = [state.settlement(only)] if only is not None else state.settlements.values()
    for s in targets:
        s.stability = clamp(s.stability + stability)
        s.prosperity = clamp(s.prosperity + prosperity)
    refresh_nation_averages(state)


def advance(nation, field, amount):
    """Raise learning or arts with diminishing returns as they approach 100."""
    value = getattr(nation, field)
    setattr(nation, field, clamp(value + amount * (1 - value / 100)))


def refresh_nation_averages(state):
    nation = state.nation
    total = state.total_population() or 1
    nation.stability = sum(s.stability * s.population for s in state.settlements.values()) / total
    nation.prosperity = sum(s.prosperity * s.population for s in state.settlements.values()) / total


def economy_year(state):
    """Run one year of the realm's economy. Returns log lines about notable outcomes."""
    nation = state.nation
    mods = state.modifiers
    notes = []
    learning_bonus = min(0.2, nation.learning / 500)
    arts_bonus = min(10.0, nation.arts / 10)
    relief = mods.get("relief", 0.0)
    hungry = []

    for s in state.settlements.values():
        fert = settlement_fertility(state, s)
        harvest = mods.get("harvest", 1.0) * mods.get(f"harvest:{s.id}", 1.0)
        irrigation = s.works.get("irrigation", 0)
        capacity = CAPACITY_PER_FERTILITY * fert * (1 + 0.2 * irrigation)
        # yields per person fall as the land fills up, so hunger limits growth
        crowding = 1.25 - 0.5 * s.population / capacity
        production = (
            s.population
            * FOOD_YIELD
            * (0.6 + 0.6 * fert)
            * crowding
            * (1 + 0.15 * irrigation)
            * harvest
            * (1 + learning_bonus)
        )
        need = s.population * FOOD_NEED
        taken = production * nation.tax_rate * TAX_FOOD_SHARE
        balance = production - taken - need
        if balance < 0:
            covered = min(-balance, need * GRANARY_COVER * s.works.get("granary", 0))
            balance += covered
        if balance < 0 and relief > 0:
            used = min(relief, -balance)
            relief -= used
            balance += used
        s.food_balance = balance

        tax_scale = nation.tax_rate / BASE_TAX
        nation.treasury.food += taken
        nation.treasury.coin += (
            s.population * COIN_PER_PERSON * tax_scale * (0.5 + s.prosperity / 100)
        )
        nation.treasury.goods += s.population * GOODS_PER_PERSON * tax_scale

        if balance < 0:
            hunger = min(1.0, -balance / need)
            s.population *= 1 - 0.3 * hunger
            s.stability = clamp(s.stability - 20 * hunger)
            s.prosperity = clamp(s.prosperity - 8 * hunger)
            hungry.append(s.name)
        else:
            rate = 0.012 + 0.008 * (s.prosperity - 50) / 50
            s.population += s.population * rate * (1 - s.population / capacity)

        plague = mods.get("plague", 0.0)
        if plague:
            s.population *= 1 - plague
        s.population = max(20.0, s.population)

        surplus_ratio = max(-0.5, min(0.5, balance / need))
        target_stab = (
            55 - (nation.tax_rate - BASE_TAX) * 150 + (s.prosperity - 45) * 0.2 + arts_bonus
        )
        s.stability = clamp(s.stability + 0.15 * (target_stab - s.stability))
        target_pros = 45 + 8 * s.works.get("roads", 0) + 20 * surplus_ratio + 50 * learning_bonus
        s.prosperity = clamp(s.prosperity + 0.1 * (target_pros - s.prosperity))

    if hungry:
        notes.append(f"Hunger in {', '.join(hungry)}.")

    # the court's upkeep
    nation.treasury.spend(COURT_UPKEEP)
    nation.treasury.add(UPKEEP_PER_PERSON, -state.total_population())
    for category, share in SPOILAGE.items():
        setattr(nation.treasury, category, nation.treasury.get(category) * (1 - share))
    if nation.treasury.coin < 0:
        adjust_settlements(state, stability=-3)
        notes.append("The treasury could not pay its way; officials went unpaid.")
    nation.treasury.clamp_nonnegative()

    # learning and the arts grow with schools and shrines, and fade without care
    schools = sum(s.works.get("school", 0) for s in state.settlements.values())
    shrines = sum(s.works.get("shrine", 0) for s in state.settlements.values())
    nation.learning *= 0.96
    nation.arts *= 0.96
    advance(nation, "learning", 0.6 * schools)
    advance(nation, "arts", 0.5 * shrines)

    refresh_nation_averages(state)
    return notes


HOUSEHOLD_SPOILAGE = {"food": 0.15, "goods": 0.05}
DEPENDANT_UPKEEP = {"food": 2.5, "coin": 0.5}  # per child or non-earning spouse
FOOD_PRICE = 1.5  # coin per food when a household has to buy


def dependants(state, char):
    """Young children (and, for the household head, a spouse) eat from this household."""
    count = sum(
        1
        for cid in char.children
        if state.character(cid)
        and state.character(cid).alive
        and state.character(cid).age(state.year) < ADULT_AGE
    )
    # count children once per couple: the father's household feeds them
    mother_of_shared = char.gender == "female" and state.character(char.spouse_id) is not None
    return 0 if mother_of_shared else count


def households_year(state):
    """Income and upkeep for every tracked adult's household. Returns notes for the player."""
    notes = []
    for char in state.living():
        if char.age(state.year) < ADULT_AGE:
            continue
        station = STATIONS[char.station]
        settlement = state.settlement(char.settlement_id)
        fert = settlement_fertility(state, settlement) if settlement else 1.0
        harvest = state.modifiers.get("harvest", 1.0)
        prosperity = (settlement.prosperity if settlement else 45) / 45
        income = {
            "food": station.income.get("food", 0) * fert * harvest,
            "coin": station.income.get("coin", 0) * prosperity,
            "goods": station.income.get("goods", 0),
        }
        char.household.add(income, char.fortune)
        char.household.spend(station.upkeep)
        char.household.add(DEPENDANT_UPKEEP, -dependants(state, char))
        for category, share in HOUSEHOLD_SPOILAGE.items():
            setattr(char.household, category, char.household.get(category) * (1 - share))
        if char.household.food < 0 and char.household.coin > 0:
            # buy what food the purse allows
            bought = min(-char.household.food, char.household.coin / FOOD_PRICE)
            char.household.food += bought
            char.household.coin -= bought * FOOD_PRICE
        if char.household.food < 0:
            char.health -= 8
            if char.is_player:
                notes.append("Your household went hungry.")
        if char.household.coin < 0:
            char.health -= 2
        char.household.clamp_nonnegative()
    return notes
