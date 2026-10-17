"""The game loop: found a nation, play a year at a time as the current character,
and when a life ends, begin the next one somewhere else in the same nation.

The UI only talks to this module: `new_game`, `options`, `choose`,
`remaining_budget`, `end_year` and `begin_next_life`.
"""

import math
from dataclasses import dataclass, field

from sankhara.constants.config import CULTURE_GROUPS
from sankhara.core.game_engine import new_seed
from sankhara.entities.namer import make_family_name
from sankhara.sim import tendencies
from sankhara.sim.actions import ACTIONS, Ctx, actions_for, budget_for, effective_cost
from sankhara.sim.events import (
    generate_events,
    obligation_key,
    resolve_events,
)
from sankhara.sim.nation import economy_year, households_year, refresh_nation_averages
from sankhara.sim.npc import npc_year
from sankhara.sim.people import (
    age_and_health,
    create_character,
    create_spouse,
    die,
    ensure_court,
    succeed,
    yearly_lifecycle,
)
from sankhara.sim.state import CATEGORIES, Budget, GameState, Nation, Settlement, Soul
from sankhara.sim.stations import ACTION_SLOTS, ADULT_AGE, STATIONS, station_title
from sankhara.sim.world import map_for_seed, tile_fertility
from sankhara.world.hexgrid import distance

KARMA_SCALE = 0.15  # how fast a year's choices move the hidden ledger
KARMA_SPENT_AT_REBIRTH = 0.5  # share of karma used up shaping the new life
REALM_RADIUS = 2
VILLAGES = 4
LOG_LIMIT = 400


# --- founding ----------------------------------------------------------------


def _pick_capital(m, rng):
    cols, rows = len(m), len(m[0])
    interior = [
        t
        for col in m
        for t in col
        if REALM_RADIUS <= t["q"] < cols - REALM_RADIUS
        and REALM_RADIUS <= t["r"] < rows - REALM_RADIUS
    ]
    interior.sort(key=tile_fertility, reverse=True)
    return rng.choice(interior[: max(1, len(interior) // 4)])


def _settlement_name(culture, rng):
    return make_family_name(culture, rng)


def new_game(seed=None):
    seed = new_seed() if seed is None else seed
    m = map_for_seed(seed)
    state = GameState(
        seed=seed,
        year=1,
        nation=Nation("", "", "", Budget(150, 60, 120), []),
        soul=Soul(),
        player_id=0,
    )
    rng = state.rng()
    capital_tile = _pick_capital(m, rng)
    culture = capital_tile["biome"].split(" ")[0]
    if culture not in CULTURE_GROUPS:
        culture = "Plain"
    nation = state.nation
    nation.culture = culture
    nation.name = make_family_name(culture, rng)
    cap = (capital_tile["q"], capital_tile["r"])
    nation.territory = [
        [t["q"], t["r"]]
        for col in m
        for t in col
        if distance(cap, (t["q"], t["r"])) <= REALM_RADIUS
    ]

    capital = Settlement(state.new_id(), _settlement_name(culture, rng), *cap, 1200.0, True)
    state.settlements[str(capital.id)] = capital
    sites = [tuple(t) for t in nation.territory if distance(cap, tuple(t)) == REALM_RADIUS]
    rng.shuffle(sites)
    for col, row in sites:
        if len(state.settlements) > VILLAGES:
            break
        if all(distance((col, row), (s.col, s.row)) >= 2 for s in state.settlements.values()):
            s = Settlement(
                state.new_id(), _settlement_name(culture, rng), col, row, rng.uniform(300, 600)
            )
            state.settlements[str(s.id)] = s
    refresh_nation_averages(state)

    # the first life: a young ruler, newly crowned
    soul_tendencies = tendencies.random_tendencies(rng, 0.2)
    ruler = create_character(
        state, "ruler", capital.id, state.year - 20, tendencies=dict(soul_tendencies)
    )
    ruler.is_player = True
    ruler.health = 85
    nation.dynasty = ruler.family_name
    nation.ruler_id = ruler.id
    state.player_id = ruler.id
    father = create_character(
        state, "noble", capital.id, state.year - 52, gender="male", family_name=ruler.family_name
    )
    mother = create_spouse(state, father)
    mother.birth_year = state.year - 46
    father.children.append(ruler.id)
    mother.children.append(ruler.id)
    ruler.father_id, ruler.mother_id = father.id, mother.id
    die(state, father, "a winter fever")
    ensure_court(state)

    state.log.append(
        f"[b]Year {state.year}[/b]  Your father has died. At twenty, {ruler.full_name} rules "
        f"{nation.name} from {capital.name}."
    )
    begin_year(state)
    return state


# --- the year ------------------------------------------------------------------


@dataclass
class Option:
    """Something the player could spend a slot on this year."""

    key: str  # plan entry: an action id, or "event:<i>" for an obligation
    action: object
    cost: dict
    pull: float  # hidden affinity; the UI uses it only to order and tint
    obligation: bool = False
    event_index: int | None = None
    blurb: str = ""


@dataclass
class YearReport:
    year: int
    lines: list[str] = field(default_factory=list)
    life_ended: bool = False


def options(state):
    """Everything the player can choose this year: obligations first, then by inclination."""
    player = state.player
    out = []
    for i, event in enumerate(state.events):
        if event.obligation:
            action = ACTIONS[event.obligation]
            out.append(
                Option(
                    obligation_key(i),
                    action,
                    effective_cost(player, action),
                    tendencies.affinity(player.tendencies, action.tags),
                    True,
                    i,
                    event.text,
                )
            )
    obligated = {o.action.id for o in out}
    regular = [
        Option(a.id, a, effective_cost(player, a), tendencies.affinity(player.tendencies, a.tags))
        for a in actions_for(state, player)
        if a.id not in obligated
    ]
    regular.sort(key=lambda o: -o.pull)
    return out + regular


def option_for(state, key):
    return next((o for o in options(state) if o.key == key), None)


def remaining_budget(state, excluding_slot=None):
    """Treasury and household left after the costs of the other planned slots."""
    player = state.player
    treasury = Budget(**{c: state.nation.treasury.get(c) for c in CATEGORIES})
    household = Budget(**{c: player.household.get(c) for c in CATEGORIES})
    for i, key in enumerate(state.plan):
        if key is None or i == excluding_slot:
            continue
        opt = option_for(state, key)
        if opt is None:
            continue
        target = (
            treasury
            if budget_for(state, player, opt.action) is state.nation.treasury
            else household
        )
        target.spend(opt.cost)
    return treasury, household


def affordable(state, opt, slot):
    treasury, household = remaining_budget(state, excluding_slot=slot)
    is_treasury = budget_for(state, state.player, opt.action) is state.nation.treasury
    return (treasury if is_treasury else household).can_afford(opt.cost)


def choose(state, slot, key):
    """Put an option in a slot (or clear it with None). Returns False if not allowed."""
    if key is None:
        state.plan[slot] = None
        return True
    if key in state.plan and state.plan.index(key) != slot:
        return False
    opt = option_for(state, key)
    if opt is None or not affordable(state, opt, slot):
        return False
    state.plan[slot] = key
    return True


def begin_year(state):
    state.modifiers = {}
    state.events = generate_events(state, state.player)
    state.plan = [None] * ACTION_SLOTS
    # habit pre-fills slots with what this character is drawn to
    state.defaults = []
    for opt in options(state):
        if len(state.defaults) >= ACTION_SLOTS:
            break
        if opt.obligation or opt.pull < tendencies.DEFAULT_THRESHOLD:
            continue
        slot = len(state.defaults)
        if choose(state, slot, opt.key):
            state.defaults.append(opt.key)


def end_year(state):
    """Carry out the plan and advance the world one year."""
    rng = state.rng()
    player = state.player
    report = YearReport(state.year)
    lines = report.lines
    karma = 0.0

    chosen_ids = set()
    for key in state.plan:
        if key is None:
            continue
        opt = option_for(state, key)
        if opt is None:
            continue
        event = state.events[opt.event_index] if opt.obligation else None
        budget_for(state, player, opt.action).spend(opt.cost)
        result = opt.action.effect(Ctx(state, player, rng, event))
        lines.append(f"{opt.action.name}: {result}")
        karma += opt.action.karma
        tendencies.strengthen(player.tendencies, opt.action.tags)
        chosen_ids.add(opt.action.id)
    for key in state.defaults:
        if key not in state.plan:
            tendencies.weaken(player.tendencies, ACTIONS[key].tags)

    notes, obligation_karma = resolve_events(state, state.plan)
    lines += notes
    karma += obligation_karma
    state.soul.karma = tendencies.clamp(state.soul.karma + KARMA_SCALE * karma)

    lines += npc_year(state)
    lines += economy_year(state)
    lines += households_year(state)
    lines += yearly_lifecycle(state)
    was_ruler = player.station == "ruler"
    note = succeed(state)
    if note:
        lines.append(note)
        if player.station == "ruler" and not was_ruler:
            lines.append("[b]The throne is yours.[/b]")

    cause = age_and_health(state, player, rng)
    if cause:
        _end_life(state, cause)
        report.life_ended = True
        lines.append(f"[b]{player.full_name} died of {cause}, aged {player.age(state.year)}.[/b]")
        note = succeed(state)
        if note:
            lines.append(note)
    else:
        ensure_court(state)

    _log(state, state.year, lines)
    state.year += 1
    if not report.life_ended:
        begin_year(state)
    return report


def _log(state, year, lines):
    body = "  ".join(lines) if lines else "A quiet year."
    state.log.append(f"[b]Year {year}[/b]  {body}")
    del state.log[:-LOG_LIMIT]


def _end_life(state, cause):
    player = state.player
    state.soul.tendencies = dict(player.tendencies)
    state.soul.lives.append(
        {
            "name": player.full_name,
            "station": station_title(player, state.nation),
            "born": player.birth_year,
            "died": state.year,
            "age": player.age(state.year),
            "cause": cause,
            "settlement": state.settlement(player.settlement_id).name,
        }
    )
    die(state, player, cause)
    state.life_over = True


# --- the next life -----------------------------------------------------------


def _wholesomeness(char):
    return sum(char.tendencies.get(t, 0) * v for t, v in tendencies.VALENCE.items()) / len(
        tendencies.VALENCE
    )


def _candidate_mothers(state, station):
    out = []
    for c in state.living():
        if c.gender != "female" or c.is_player or not (18 <= c.age(state.year) <= 40):
            continue
        husband = state.character(c.spouse_id)
        if not husband or not husband.alive:
            continue
        if station == "ruler":
            if husband.id == state.nation.ruler_id or c.id == state.nation.ruler_id:
                out.append((c, husband))
            elif husband.family_name == state.nation.dynasty:
                out.append((c, husband))
        elif husband.station == station and husband.family_name != state.nation.dynasty:
            out.append((c, husband))
    return out


def _new_parents(state, station, karma, rng):
    settlements = list(state.settlements.values())
    if station in ("farmer", "artisan"):
        settlements = [s for s in settlements if not s.is_capital] or settlements
    elif station in ("noble", "ruler"):
        settlements = [s for s in settlements if s.is_capital]
    home = rng.choice(settlements)
    father_station = "noble" if station == "ruler" else station
    father = create_character(
        state, father_station, home.id, state.year - rng.randint(22, 38), gender="male"
    )
    mother = create_spouse(state, father)
    mother.birth_year = state.year - rng.randint(19, 34)
    for parent in (father, mother):
        for t, v in tendencies.VALENCE.items():
            parent.tendencies[t] = tendencies.clamp(parent.tendencies.get(t, 0) + 0.3 * karma * v)
    return mother, father


def begin_next_life(state):
    """Begin a new life in the same nation and fast-forward through childhood.

    Returns lines describing the birth and the years of childhood.
    """
    rng = state.rng()
    soul = state.soul
    karma = soul.karma
    weights = {s.id: s.rebirth_weight for s in STATIONS.values()}
    station = rng.choices(list(weights), list(weights.values()))[0]

    candidates = _candidate_mothers(state, station)
    if candidates:
        # better karma, kinder parents
        w = [math.exp(2 * karma * (_wholesomeness(m) + _wholesomeness(f))) for m, f in candidates]
        mother, father = rng.choices(candidates, w)[0]
    else:
        mother, father = _new_parents(state, station, karma, rng)

    child_station = father.station if father.station != "ruler" else "noble"
    child = create_character(
        state,
        child_station,
        father.settlement_id,
        state.year,
        mother=mother,
        father=father,
        tendencies=tendencies.carry_into_next_life(soul.tendencies, karma),
    )
    child.is_player = True
    child.health = max(40.0, min(100.0, 78 + 18 * karma + rng.uniform(-8, 8)))
    child.fortune = max(0.5, 1 + 0.35 * karma + rng.uniform(-0.1, 0.1))
    child.family_stability = max(0.3, 1 - 0.5 * karma)
    for parent in (mother, father):
        warmth = 0.2 + 0.5 * karma + rng.uniform(-0.2, 0.2)
        parent.adjust_affinity(child.id, warmth)
        child.adjust_affinity(parent.id, warmth)
    soul.karma *= 1 - KARMA_SPENT_AT_REBIRTH
    state.player.is_player = False
    state.player_id = child.id
    state.life_over = False

    home = state.settlement(child.settlement_id)
    lines = [
        f"[b]Year {state.year}[/b]  {child.full_name} was born in {home.name} to "
        f"{mother.full_name} and {father.full_name}, "
        f"{STATIONS[father.station].title.lower()}{'s' if father.station != 'ruler' else ''}."
    ]
    if father.station == "ruler" or father.family_name == state.nation.dynasty:
        lines[0] = lines[0].rsplit(",", 1)[0] + ", of the ruling house."

    # childhood passes without the player's hand
    for _ in range(ADULT_AGE):
        state.modifiers = {}
        notable = [
            e.text
            for e in generate_events(state, child, national_only=True)
            if e.kind in ("drought", "plague", "flood")
        ]
        npc_year(state, protect={child.id})
        economy_year(state)
        households_year(state)
        notable += yearly_lifecycle(state, protect={child.id})
        note = succeed(state)
        if note:
            notable.append(note)
        if notable:
            _log(state, state.year, notable)
            lines.append(f"[b]Year {state.year}[/b]  " + "  ".join(notable))
        state.year += 1

    child.household = Budget(**STATIONS[child.station].start)
    child.household.add(STATIONS[child.station].start, child.fortune - 1)
    child.household.clamp_nonnegative()
    ensure_court(state)
    lines.append(
        f"[b]Year {state.year}[/b]  {child.name} is {ADULT_AGE} and must find their own way."
    )
    state.log.append(lines[-1])
    begin_year(state)
    return lines


def life_summary(state):
    """The most recent finished life, for the end-of-life screen."""
    return state.soul.lives[-1] if state.soul.lives else None
