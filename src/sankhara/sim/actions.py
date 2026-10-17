"""What a character can do with a year's attention.

Every station has its own set of actions with a different reach: a ruler's are
broad and slow and draw on the treasury, a farmer's are local and immediate and
draw on the household. Each action carries tendency tags and a hidden karma
value reflecting the intention behind it, never its outcome.

Effects receive a Ctx and return a short sentence for the log.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from sankhara.sim import tendencies
from sankhara.sim.nation import WORK_CAPS, adjust_settlements, advance, clamp
from sankhara.sim.people import create_spouse, family_of, heir_of
from sankhara.sim.stations import ADULT_AGE
from sankhara.sim.world import settlement_fertility


@dataclass
class Ctx:
    state: object
    char: object
    rng: object
    event: object = None

    @property
    def nation(self):
        return self.state.nation

    @property
    def settlement(self):
        return self.state.settlement(self.char.settlement_id)


@dataclass(frozen=True)
class Action:
    id: str
    name: str
    text: str
    stations: tuple  # empty = open to every station
    tags: tuple
    karma: float  # hidden: the intention, not the outcome
    effect: Callable = field(repr=False)
    cost: dict = field(default_factory=dict)
    scope: str = "station"  # "station" spends the treasury for rulers; "own" always the household
    requires: Callable | None = field(default=None, repr=False)
    obligation_only: bool = False


def budget_for(state, char, action):
    if action.scope == "station" and char.station == "ruler":
        return state.nation.treasury
    return char.household


def effective_cost(char, action):
    mult = tendencies.cost_multiplier(char.tendencies, action.tags)
    return {k: round(v * mult, 1) for k, v in action.cost.items()}


# --- helpers ---------------------------------------------------------------


def _family(ctx):
    return [c for _, c in family_of(ctx.state, ctx.char)]


def _neediest(ctx, work):
    sites = _open_sites(ctx.state, work)
    return min(sites, key=lambda s: s.food_balance / max(1, s.population))


def _build(ctx, settlement, work):
    settlement.works[work] = min(WORK_CAPS[work], settlement.works.get(work, 0) + 1)
    return settlement.works[work]


def _open_sites(state, work):
    return [s for s in state.settlements.values() if s.works.get(work, 0) < WORK_CAPS[work]]


def _can_build(work):
    return lambda state, char: bool(_open_sites(state, work))


def _local(ctx, stability=0.0, prosperity=0.0):
    adjust_settlements(
        ctx.state, stability=stability, prosperity=prosperity, only=ctx.char.settlement_id
    )


def _realm(ctx, stability=0.0, prosperity=0.0):
    adjust_settlements(ctx.state, stability=stability, prosperity=prosperity)


def _heal(char, amount):
    char.health = clamp(char.health + amount)


def _neighbour(ctx):
    s_id = ctx.char.settlement_id
    family = {c.id for c in _family(ctx)}
    near = [
        c
        for c in ctx.state.living()
        if c.settlement_id == s_id and not c.is_player and c.id not in family
    ]
    return ctx.rng.choice(near) if near else None


# --- generic actions ---------------------------------------------------------


def _care_family(ctx):
    fam = _family(ctx)
    for c in fam:
        _heal(c, 5)
        c.adjust_affinity(ctx.char.id, 0.1)
        ctx.char.adjust_affinity(c.id, 0.05)
    return "Your family was looked after." if fam else "There was little family to tend."


def _rest(ctx):
    _heal(ctx.char, 10)
    return "You rested and recovered some strength."


def _reflect(ctx):
    _heal(ctx.char, 4)
    return "The year passed quietly."


def _revel(ctx):
    _heal(ctx.char, 2)
    friend = _neighbour(ctx)
    if friend:
        friend.adjust_affinity(ctx.char.id, 0.1)
    return "There was feasting and good company."


def _seek_match(ctx):
    if ctx.rng.random() < 0.6:
        spouse = create_spouse(ctx.state, ctx.char)
        return f"You married {spouse.full_name}."
    return "No match came of it this year."


def _raise_children(ctx):
    kids = [
        ctx.state.character(c)
        for c in ctx.char.children
        if ctx.state.character(c) and ctx.state.character(c).alive
    ]
    for kid in kids:
        tendencies.pull_toward(kid.tendencies, ctx.char.tendencies, 0.15)
        kid.adjust_affinity(ctx.char.id, 0.1)
    return "Your children grew under your eye."


def _has_young_children(state, char):
    return any(
        state.character(c) and state.character(c).alive and state.character(c).age(state.year) < 20
        for c in char.children
    )


def _unmarried(state, char):
    return char.spouse_id is None and char.age(state.year) <= 45


# --- ruler -------------------------------------------------------------------


def _hold_court(ctx):
    _realm(ctx, stability=4)
    return "Petitions were heard; people felt listened to."


def _raise_taxes(ctx):
    ctx.nation.tax_rate = min(0.4, round(ctx.nation.tax_rate + 0.03, 2))
    _realm(ctx, stability=-4)
    return f"Taxes rose to {ctx.nation.tax_rate:.0%}."


def _lower_taxes(ctx):
    ctx.nation.tax_rate = max(0.05, round(ctx.nation.tax_rate - 0.03, 2))
    _realm(ctx, stability=3, prosperity=2)
    return f"Taxes fell to {ctx.nation.tax_rate:.0%}."


def _irrigation(ctx):
    s = _neediest(ctx, "irrigation")
    level = _build(ctx, s, "irrigation")
    return f"Channels were dug at {s.name} (irrigation {level})."


def _granary(ctx):
    s = _neediest(ctx, "granary")
    level = _build(ctx, s, "granary")
    return f"Granaries were raised at {s.name} (granary {level})."


def _school(ctx):
    s = max(
        ctx.state.settlements.values(), key=lambda s: s.population - 400 * s.works.get("school", 0)
    )
    _build(ctx, s, "school")
    advance(ctx.nation, "learning", 3)
    return f"A school was endowed at {s.name}."


def _shrine(ctx):
    s = max(
        ctx.state.settlements.values(), key=lambda s: s.population - 400 * s.works.get("shrine", 0)
    )
    _build(ctx, s, "shrine")
    advance(ctx.nation, "arts", 3)
    _local(ctx, stability=1)
    return f"A shrine was raised at {s.name}."


def _roads(ctx):
    s = min(_open_sites(ctx.state, "roads"), key=lambda s: s.works.get("roads", 0))
    _build(ctx, s, "roads")
    return f"Roads were laid to {s.name}."


def _display(ctx):
    _realm(ctx, stability=5)
    advance(ctx.nation, "arts", 1)
    return "The capital was dazzled; for a while, people talked of little else."


def _relieve(ctx):
    ctx.state.modifiers["relief"] = ctx.state.modifiers.get("relief", 0.0) + 60
    _realm(ctx, stability=2)
    return "The royal stores were opened to the hungry."


def _tutor_heir(ctx):
    heir = heir_of(ctx.state)
    if not heir or heir.is_player:
        return "There was no heir to teach."
    tendencies.pull_toward(heir.tendencies, ctx.char.tendencies, 0.15)
    heir.adjust_affinity(ctx.char.id, 0.1)
    return f"You spent the year shaping {heir.name}."


def _has_heir(state, char):
    heir = heir_of(state)
    return heir is not None and not heir.is_player and heir.age(state.year) < 30


def _seize(ctx):
    nobles = [c for c in ctx.state.living() if c.station == "noble" and not c.is_player]
    if not nobles:
        return "There was no estate worth taking."
    victim = max(nobles, key=lambda c: c.household.coin)
    taken = victim.household.coin * 0.6
    victim.household.coin -= taken
    ctx.nation.treasury.coin += taken + 20
    victim.adjust_affinity(ctx.char.id, -0.5)
    _realm(ctx, stability=-3)
    return f"The estates of {victim.full_name} were seized."


# --- noble -------------------------------------------------------------------


def _administer(ctx):
    _local(ctx, stability=2, prosperity=1)
    ctx.char.household.coin += 4
    return "Your lands were well run."


def _skim(ctx):
    amount = min(15, ctx.nation.treasury.coin)
    ctx.nation.treasury.coin -= amount
    ctx.char.household.coin += amount
    _realm(ctx, stability=-1)
    return "The accounts balanced, on paper."


def _counsel(ctx):
    ruler = ctx.state.ruler
    if not ruler or ruler.is_player:
        return "There was no one to counsel."
    tendencies.pull_toward(ruler.tendencies, ctx.char.tendencies, 0.1)
    ruler.adjust_affinity(ctx.char.id, 0.1)
    return f"{ruler.name} listened to your counsel."


def _patronise(ctx):
    advance(ctx.nation, "arts", 2)
    return "Painters and poets found a patron in you."


def _hunt(ctx):
    _heal(ctx.char, 2)
    for c in ctx.state.living():
        if c.station == "noble" and not c.is_player:
            c.adjust_affinity(ctx.char.id, 0.05)
    return "The hunt was good and the company better."


def _judge(ctx):
    _local(ctx, stability=3)
    return "A quarrel was settled fairly."


def _squeeze(ctx):
    ctx.char.household.food += 10
    ctx.char.household.coin += 6
    _local(ctx, stability=-2, prosperity=-2)
    return "Your tenants paid more than they could spare."


# --- scholar -------------------------------------------------------------------


def _teach(ctx):
    advance(ctx.nation, "learning", 1.5)
    ctx.char.household.coin += 2
    return "Your pupils learned their letters."


def _study(ctx):
    advance(ctx.nation, "learning", 1)
    return "You read deep into the old texts."


def _tend_sick(ctx):
    _local(ctx, stability=1)
    s = ctx.settlement
    s.population *= 1.005
    if ctx.rng.random() < 0.2:
        _heal(ctx.char, -10)
        return "You nursed the sick, and caught a fever for your trouble."
    return "You nursed the sick through the cold months."


def _rites(ctx):
    _local(ctx, stability=2)
    advance(ctx.nation, "arts", 1)
    return "The seasonal rites were kept."


def _patron(ctx):
    ctx.char.household.coin += 10
    return "A wealthy patron took an interest in you."


def _solitude(ctx):
    _heal(ctx.char, 5)
    for c in _family(ctx):
        c.adjust_affinity(ctx.char.id, -0.05)
    return "You withdrew from the world for a season."


def _treatise(ctx):
    advance(ctx.nation, "learning", 3)
    advance(ctx.nation, "arts", 1)
    return "Your treatise was copied and passed around."


# --- merchant ------------------------------------------------------------------


def _caravan(ctx):
    _local(ctx, prosperity=1)
    if ctx.rng.random() < 0.7:
        ctx.char.household.coin += 24
        return "The caravan came back laden."
    return "The caravan was lost on the road."


def _hoard(ctx):
    ctx.char.household.food += 25
    if ctx.settlement.food_balance < 0:
        _local(ctx, stability=-3, prosperity=-2)
        return "You bought up grain while others went short."
    return "Your stores filled with grain."


def _sell_fair(ctx):
    ctx.char.household.food -= 15
    ctx.char.household.coin += 12
    ctx.state.modifiers["relief"] = ctx.state.modifiers.get("relief", 0.0) + 15
    return "You sold grain at a fair price."


def _has_grain(state, char):
    return char.household.food >= 15


def _fund_works(ctx):
    s = ctx.settlement
    if s.works.get("roads", 0) >= WORK_CAPS["roads"]:
        _local(ctx, prosperity=2)
        return f"You paid to mend the roads around {s.name}."
    _build(ctx, s, "roads")
    return f"You paid for a new road at {s.name}."


def _lend(ctx):
    if ctx.rng.random() < 0.85:
        ctx.char.household.coin += 22
        return "Your loans were repaid with interest."
    return "A debtor vanished with your money."


def _festival(ctx):
    advance(ctx.nation, "arts", 1)
    _local(ctx, stability=2)
    return "The festival was the talk of the season."


def _shave(ctx):
    ctx.char.household.coin += 10
    if ctx.rng.random() < 0.25:
        ctx.char.household.coin -= 14
        _local(ctx, stability=-1)
        return "You were caught shaving the weights and fined."
    return "No one noticed the weights were light."


# --- artisan -------------------------------------------------------------------


def _craft(ctx):
    ctx.char.household.goods += 8
    ctx.char.household.coin += 3
    return "Your work sold steadily."


def _commission(ctx):
    ctx.char.household.coin += 12
    ctx.char.household.goods -= 3
    return "A grand commission paid well."


def _apprentice(ctx):
    _local(ctx, prosperity=1)
    advance(ctx.nation, "learning", 0.3)
    return "Your apprentice is shaping up."


def _experiment(ctx):
    if ctx.rng.random() < 0.35:
        advance(ctx.nation, "learning", 2)
        ctx.char.household.goods += 5
        return "A new technique worked!"
    return "The experiments came to nothing."


def _repair(ctx):
    _local(ctx, stability=2, prosperity=1)
    return "The common buildings were mended."


def _cut_corners(ctx):
    ctx.char.household.coin += 8
    _local(ctx, prosperity=-1)
    return "Your work was quicker, and worse."


def _guild_drink(ctx):
    friend = _neighbour(ctx)
    if friend:
        friend.adjust_affinity(ctx.char.id, 0.1)
    return "The guild hall was loud late into the night."


# --- farmer --------------------------------------------------------------------


def _fields(ctx):
    fert = settlement_fertility(ctx.state, ctx.settlement)
    gained = 14 * fert * ctx.state.modifiers.get("harvest", 1.0)
    ctx.char.household.food += gained
    return f"The fields yielded {gained:.0f} measures."


def _clear_land(ctx):
    ctx.char.household.food += 4
    ctx.char.fortune = min(1.5, ctx.char.fortune + 0.05)
    return "New ground was broken."


def _help_neighbour(ctx):
    friend = _neighbour(ctx)
    _local(ctx, prosperity=1)
    if friend:
        friend.adjust_affinity(ctx.char.id, 0.15)
        return f"You helped {friend.full_name} bring in the harvest."
    return "You helped bring in a neighbour's harvest."


def _market(ctx):
    ctx.char.household.coin += 6
    return "You sold your produce at market."


def _offering(ctx):
    _local(ctx, stability=1)
    return "You brought an offering to the shrine."


def _poach(ctx):
    ctx.char.household.food += 8
    if ctx.rng.random() < 0.25:
        ctx.char.household.coin -= 6
        _heal(ctx.char, -5)
        return "The lord's men caught you poaching."
    return "There was meat on the table."


def _tavern(ctx):
    _heal(ctx.char, -1)
    friend = _neighbour(ctx)
    if friend:
        friend.adjust_affinity(ctx.char.id, 0.05)
    return "The tavern was warm."


# --- obligations (offered only when an event calls for them) -------------------


def _tend_relative(ctx):
    target = ctx.state.character(ctx.event.target_id) if ctx.event else None
    if target and target.alive:
        _heal(target, 15)
        target.adjust_affinity(ctx.char.id, 0.25)
        return f"You stayed at {target.name}'s side."
    return "You came, but too late."


def _shelter(ctx):
    ctx.char.household.food = max(0.0, ctx.char.household.food - 3)
    return "The stranger slept by your fire and left at dawn."


def _grievances(ctx):
    if ctx.char.station == "ruler":
        _realm(ctx, stability=6)
    else:
        _local(ctx, stability=4)
    return "Grievances were heard and some were answered."


def _share_food(ctx):
    given = min(10.0, ctx.char.household.food)
    ctx.char.household.food -= given
    ctx.state.modifiers["relief"] = ctx.state.modifiers.get("relief", 0.0) + given
    return "You shared what you had."


def _settle_debt(ctx):
    target = ctx.state.character(ctx.event.target_id) if ctx.event else None
    given = min(10.0, ctx.char.household.coin)
    ctx.char.household.coin -= given
    if target:
        target.household.coin += given
        target.adjust_affinity(ctx.char.id, 0.3)
    return "You paid a relative's debt."


def _watchmen(ctx):
    _realm(ctx, prosperity=2)
    return "Watchmen were posted on the roads."


def _rebuild(ctx):
    _local(ctx, stability=2, prosperity=2)
    return "You helped rebuild what the fire took."


ACTIONS = {
    a.id: a
    for a in [
        # everyone
        Action(
            "care_family",
            "Look after your family",
            "Time and care for those closest to you.",
            (),
            ("caring",),
            0.04,
            _care_family,
            {"food": 2},
            scope="own",
        ),
        Action("rest", "Rest and recover", "Let the body mend.", (), (), 0.0, _rest, scope="own"),
        Action(
            "reflect",
            "Spend the year quietly",
            "Walk, think, keep your own counsel.",
            (),
            ("contemplative",),
            0.05,
            _reflect,
            scope="own",
        ),
        Action(
            "revel",
            "Feast and make merry",
            "Good food, good drink, good friends.",
            (),
            ("indulgent",),
            -0.04,
            _revel,
            {"food": 3, "coin": 2},
            scope="own",
        ),
        Action(
            "seek_match",
            "Seek a match",
            "Find someone to share your life with.",
            (),
            ("caring", "ambitious"),
            0.0,
            _seek_match,
            {"coin": 3},
            scope="own",
            requires=_unmarried,
        ),
        Action(
            "raise_children",
            "Raise your children",
            "Your children learn from how you live.",
            (),
            ("caring",),
            0.03,
            _raise_children,
            scope="own",
            requires=_has_young_children,
        ),
        # ruler
        Action(
            "hold_court",
            "Hold court",
            "Hear petitions from across the realm.",
            ("ruler",),
            ("caring", "diligent"),
            0.05,
            _hold_court,
            {"coin": 20},
        ),
        Action(
            "raise_taxes",
            "Raise taxes",
            "More for the treasury, less for everyone else.",
            ("ruler",),
            ("acquisitive", "harsh"),
            -0.06,
            _raise_taxes,
        ),
        Action(
            "lower_taxes",
            "Lower taxes",
            "Ease the burden on your people.",
            ("ruler",),
            ("generous",),
            0.05,
            _lower_taxes,
        ),
        Action(
            "irrigation",
            "Commission irrigation",
            "Dig channels where the harvest is poorest.",
            ("ruler",),
            ("diligent",),
            0.01,
            _irrigation,
            {"coin": 60, "goods": 40},
            requires=_can_build("irrigation"),
        ),
        Action(
            "granary",
            "Build granaries",
            "Store against bad years.",
            ("ruler",),
            ("diligent", "caring"),
            0.02,
            _granary,
            {"coin": 40, "goods": 30},
            requires=_can_build("granary"),
        ),
        Action(
            "school",
            "Endow a school",
            "Learning, slowly, for everyone.",
            ("ruler",),
            ("studious", "generous"),
            0.03,
            _school,
            {"coin": 50, "goods": 20},
            requires=_can_build("school"),
        ),
        Action(
            "shrine",
            "Raise a shrine",
            "A place for rites and for art.",
            ("ruler",),
            ("contemplative", "generous"),
            0.03,
            _shrine,
            {"coin": 45, "goods": 25},
            requires=_can_build("shrine"),
        ),
        Action(
            "roads",
            "Lay roads",
            "Trade follows the road.",
            ("ruler",),
            ("diligent", "ambitious"),
            0.01,
            _roads,
            {"coin": 40, "goods": 30},
            requires=_can_build("roads"),
        ),
        Action(
            "display",
            "Stage a grand display",
            "Remind everyone who rules.",
            ("ruler",),
            ("indulgent", "ambitious"),
            -0.05,
            _display,
            {"coin": 50, "food": 40},
        ),
        Action(
            "relieve",
            "Open the royal stores",
            "Feed those who are going hungry.",
            ("ruler",),
            ("generous", "caring"),
            0.08,
            _relieve,
            {"food": 60},
        ),
        Action(
            "tutor_heir",
            "Tutor your heir",
            "Shape the one who comes after you.",
            ("ruler",),
            ("caring", "studious"),
            0.03,
            _tutor_heir,
            {"coin": 5},
            requires=_has_heir,
        ),
        Action(
            "seize",
            "Seize a noble's estates",
            "The crown's need is greater.",
            ("ruler",),
            ("acquisitive", "harsh"),
            -0.1,
            _seize,
        ),
        # noble
        Action(
            "administer",
            "Administer your lands",
            "Keep your holdings orderly.",
            ("noble",),
            ("diligent",),
            0.02,
            _administer,
        ),
        Action(
            "skim",
            "Skim from the levies",
            "Who would notice a little?",
            ("noble",),
            ("acquisitive",),
            -0.07,
            _skim,
        ),
        Action(
            "counsel",
            "Counsel the ruler",
            "Bend the ruler's ear your way.",
            ("noble",),
            ("ambitious", "studious"),
            0.02,
            _counsel,
        ),
        Action(
            "patronise",
            "Patronise artists",
            "Fund painters and poets.",
            ("noble",),
            ("generous",),
            0.03,
            _patronise,
            {"coin": 10},
        ),
        Action(
            "hunt",
            "Hunt with your peers",
            "Sport, wine and alliances.",
            ("noble",),
            ("indulgent",),
            -0.03,
            _hunt,
            {"coin": 6, "food": 4},
        ),
        Action(
            "judge",
            "Judge local disputes",
            "Settle quarrels fairly.",
            ("noble",),
            ("caring", "diligent"),
            0.04,
            _judge,
        ),
        Action(
            "squeeze",
            "Squeeze your tenants",
            "Rents are what you say they are.",
            ("noble",),
            ("harsh", "acquisitive"),
            -0.08,
            _squeeze,
        ),
        # scholar
        Action(
            "teach",
            "Teach the young",
            "Letters and numbers for whoever comes.",
            ("scholar",),
            ("generous", "studious"),
            0.04,
            _teach,
        ),
        Action(
            "study",
            "Study the old texts",
            "Read, copy, understand.",
            ("scholar",),
            ("studious", "contemplative"),
            0.02,
            _study,
        ),
        Action(
            "tend_sick",
            "Tend the sick",
            "Nurse those no one else will.",
            ("scholar",),
            ("caring", "generous"),
            0.07,
            _tend_sick,
            {"food": 2},
        ),
        Action(
            "rites",
            "Lead the seasonal rites",
            "Keep the old observances.",
            ("scholar",),
            ("contemplative", "caring"),
            0.03,
            _rites,
        ),
        Action(
            "patron",
            "Court a wealthy patron",
            "Learning needs funding.",
            ("scholar",),
            ("ambitious", "acquisitive"),
            -0.02,
            _patron,
        ),
        Action(
            "solitude",
            "Withdraw into solitude",
            "Leave the world alone for a while.",
            ("scholar",),
            ("contemplative",),
            0.04,
            _solitude,
        ),
        Action(
            "treatise",
            "Write a treatise",
            "Put your understanding into words.",
            ("scholar",),
            ("studious", "ambitious"),
            0.0,
            _treatise,
            {"goods": 2, "coin": 2},
        ),
        # merchant
        Action(
            "caravan",
            "Send a caravan",
            "Risk goods for profit on the roads.",
            ("merchant",),
            ("ambitious", "diligent"),
            0.0,
            _caravan,
            {"goods": 8, "coin": 4},
        ),
        Action(
            "hoard",
            "Buy up grain",
            "Buy cheap, sell dear.",
            ("merchant",),
            ("acquisitive",),
            -0.08,
            _hoard,
            {"coin": 12},
        ),
        Action(
            "sell_fair",
            "Sell grain at a fair price",
            "Feed people without fleecing them.",
            ("merchant",),
            ("caring", "diligent"),
            0.04,
            _sell_fair,
            requires=_has_grain,
        ),
        Action(
            "fund_works",
            "Fund a public work",
            "Pay for a road others will use.",
            ("merchant",),
            ("generous",),
            0.06,
            _fund_works,
            {"coin": 25},
        ),
        Action(
            "lend",
            "Lend at interest",
            "Money makes money.",
            ("merchant",),
            ("acquisitive",),
            -0.02,
            _lend,
            {"coin": 15},
        ),
        Action(
            "festival",
            "Sponsor a festival",
            "Music and lanterns, at your expense.",
            ("merchant",),
            ("generous", "indulgent"),
            0.01,
            _festival,
            {"coin": 15, "food": 5},
        ),
        Action(
            "shave",
            "Shave the weights",
            "A little light on every scale.",
            ("merchant",),
            ("acquisitive", "harsh"),
            -0.09,
            _shave,
        ),
        # artisan
        Action(
            "craft",
            "Craft goods for market",
            "Honest work, steadily sold.",
            ("artisan",),
            ("diligent",),
            0.01,
            _craft,
        ),
        Action(
            "commission",
            "Take a grand commission",
            "Work for the wealthy.",
            ("artisan",),
            ("ambitious",),
            0.0,
            _commission,
        ),
        Action(
            "apprentice",
            "Train an apprentice",
            "Pass on what you know.",
            ("artisan",),
            ("generous", "caring"),
            0.04,
            _apprentice,
        ),
        Action(
            "experiment",
            "Experiment with techniques",
            "Most attempts fail.",
            ("artisan",),
            ("studious",),
            0.01,
            _experiment,
            {"goods": 3},
        ),
        Action(
            "repair",
            "Repair the commons",
            "Mend what everyone uses.",
            ("artisan",),
            ("generous",),
            0.05,
            _repair,
            {"goods": 4},
        ),
        Action(
            "cut_corners",
            "Cut corners",
            "Faster, cheaper, worse.",
            ("artisan",),
            ("acquisitive",),
            -0.05,
            _cut_corners,
        ),
        Action(
            "guild_drink",
            "Drink with the guild",
            "The guild hall stays open late.",
            ("artisan",),
            ("indulgent",),
            -0.02,
            _guild_drink,
            {"coin": 3},
        ),
        # farmer
        Action(
            "fields",
            "Work the fields",
            "From first light to last.",
            ("farmer",),
            ("diligent",),
            0.01,
            _fields,
        ),
        Action(
            "clear_land",
            "Clear new land",
            "More ground, for later.",
            ("farmer",),
            ("diligent", "ambitious"),
            0.0,
            _clear_land,
        ),
        Action(
            "help_neighbour",
            "Help a neighbour's harvest",
            "They'd do the same. Maybe.",
            ("farmer",),
            ("generous", "caring"),
            0.06,
            _help_neighbour,
        ),
        Action(
            "market",
            "Take produce to market",
            "Turn grain into coin.",
            ("farmer",),
            ("ambitious",),
            0.0,
            _market,
            {"food": 8},
        ),
        Action(
            "offering",
            "Bring an offering to the shrine",
            "A share of the harvest.",
            ("farmer",),
            ("contemplative", "generous"),
            0.03,
            _offering,
            {"food": 3},
        ),
        Action(
            "poach",
            "Poach in the lord's woods",
            "Hungry is hungry.",
            ("farmer",),
            ("acquisitive",),
            -0.04,
            _poach,
        ),
        Action(
            "tavern",
            "Drink at the tavern",
            "A warm room and loose talk.",
            ("farmer",),
            ("indulgent",),
            -0.02,
            _tavern,
            {"coin": 2},
        ),
        # obligations
        Action(
            "tend_relative",
            "Tend to them",
            "Be there while they are ill.",
            (),
            ("caring",),
            0.05,
            _tend_relative,
            scope="own",
            obligation_only=True,
        ),
        Action(
            "shelter",
            "Give the stranger shelter",
            "A meal and a place by the fire.",
            (),
            ("generous",),
            0.05,
            _shelter,
            scope="own",
            obligation_only=True,
        ),
        Action(
            "grievances",
            "Hear the grievances",
            "Something has to be done.",
            ("ruler", "noble"),
            ("caring", "diligent"),
            0.04,
            _grievances,
            {"coin": 10},
            obligation_only=True,
        ),
        Action(
            "share_food",
            "Share your food",
            "Your neighbours are hungry.",
            (),
            ("generous",),
            0.06,
            _share_food,
            scope="own",
            obligation_only=True,
        ),
        Action(
            "settle_debt",
            "Pay their debt",
            "Family is family.",
            (),
            ("generous", "caring"),
            0.05,
            _settle_debt,
            scope="own",
            obligation_only=True,
        ),
        Action(
            "watchmen",
            "Post watchmen on the roads",
            "Make the roads safe again.",
            ("ruler",),
            ("diligent", "caring"),
            0.03,
            _watchmen,
            {"coin": 25},
            obligation_only=True,
        ),
        Action(
            "rebuild",
            "Help rebuild",
            "The fire took homes as well as stores.",
            (),
            ("generous", "diligent"),
            0.04,
            _rebuild,
            scope="own",
            obligation_only=True,
        ),
    ]
}


def actions_for(state, char):
    """Ordinary actions open to this character this year (no obligations)."""
    out = []
    for a in ACTIONS.values():
        if a.obligation_only:
            continue
        if a.stations and char.station not in a.stations:
            continue
        if a.requires and not a.requires(state, char):
            continue
        out.append(a)
    return out


def is_adult(state, char):
    return char.age(state.year) >= ADULT_AGE
