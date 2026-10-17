"""The game loop: a small people at the start of everything, played a year at a time as
the current character; when a life ends, the next begins somewhere else among the
same people.

The UI only talks to this module: `new_game`, `options`, `choose`, `affordable`,
`remaining_budget`, `end_year`, `choose_form` and `begin_next_life`.
"""

import math
from dataclasses import dataclass, field

from sankhara.constants.config import CULTURE_GROUPS
from sankhara.core.game_engine import new_seed
from sankhara.entities.namer import make_family_name
from sankhara.sim import discoveries, projects, tendencies
from sankhara.sim.actions import ACTIONS, Ctx, actions_for, budget_for, effective_cost
from sankhara.sim.events import generate_events, obligation_key, resolve_events
from sankhara.sim.nation import (
    capacity,
    economy_year,
    hands_available,
    households_year,
    refresh_averages,
)
from sankhara.sim.npc import npc_year
from sankhara.sim.people import (
    age_and_health,
    child_role,
    create_character,
    create_spouse,
    die,
    ensure_elders,
    succeed,
    yearly_lifecycle,
)
from sankhara.sim.peoples import neighbours_year, place_neighbours
from sankhara.sim.state import Budget, GameState, Nation, Settlement, Soul
from sankhara.sim.stations import ACTION_SLOTS, ADULT_AGE, STATIONS, rebirth_weights, station_title
from sankhara.sim.world import all_tiles, forage_value, map_for_seed, place_name
from sankhara.world.hexgrid import distance

KARMA_SCALE = 0.15  # how fast a year's choices move the hidden ledger
FORM_KARMA = 0.3  # how much choosing the shape of a custom weighs, relative to a deed
KARMA_SPENT_AT_REBIRTH = 0.5  # share of karma used up shaping the new life
RANGE_RADIUS = 2
CAMPS = 3
START_FILL = 0.42  # how full each camp's land is at the start
LOG_LIMIT = 400


# --- founding ----------------------------------------------------------------


def _culture_for(t):
    culture = t["biome"].split(" ")[0]
    return culture if culture in CULTURE_GROUPS else "Plain"


def _pick_seat(m, rng):
    cols, rows = len(m), len(m[0])
    interior = [
        t
        for t in all_tiles(m)
        if RANGE_RADIUS <= t["q"] < cols - RANGE_RADIUS
        and RANGE_RADIUS <= t["r"] < rows - RANGE_RADIUS
    ]
    interior.sort(key=forage_value, reverse=True)
    return rng.choice(interior[: max(1, len(interior) // 4)])


def new_game(seed=None):
    seed = new_seed() if seed is None else seed
    m = map_for_seed(seed)
    state = GameState(
        seed=seed,
        year=1,
        nation=Nation("", "", Budget({"food": 40.0, "hands": 0.0}), []),
        soul=Soul(),
        player_id=0,
    )
    rng = state.rng()
    seat_tile = _pick_seat(m, rng)
    culture = _culture_for(seat_tile)
    nation = state.nation
    nation.culture = culture
    nation.name = make_family_name(culture, rng)
    seat = (seat_tile["q"], seat_tile["r"])
    nation.territory = [
        [t["q"], t["r"]] for t in all_tiles(m) if distance(seat, (t["q"], t["r"])) <= RANGE_RADIUS
    ]
    for did in discoveries.START_KNOWN:
        d = discoveries.DISCOVERIES[did]
        nation.known[did] = rng.choice(d.forms).id if d.forms else ""

    home = Settlement(state.new_id(), place_name(state, culture, rng), *seat, 0.0, is_seat=True)
    state.settlements[str(home.id)] = home
    sites = [tuple(t) for t in nation.territory if distance(seat, tuple(t)) == RANGE_RADIUS]
    rng.shuffle(sites)
    for col, row in sites:
        if len(state.settlements) >= CAMPS:
            break
        if all(distance((col, row), (s.col, s.row)) >= 2 for s in state.settlements.values()):
            s = Settlement(state.new_id(), place_name(state, culture, rng), col, row, 0.0)
            state.settlements[str(s.id)] = s
    for s in state.settlements.values():
        s.population = max(50.0, START_FILL * capacity(state, s) * rng.uniform(0.9, 1.1))
    refresh_averages(state)
    nation.stores.set("hands", hands_available(state))

    place_neighbours(state, _culture_for, rng)
    for d in rng.sample(discoveries.available(state), 3):
        nation.insight[d.id] = d.cost * rng.uniform(0.15, 0.35)

    # the first life: a young leader, whose mother led the people before
    leader = create_character(
        state,
        "leader",
        home.id,
        state.year - 20,
        tendencies=tendencies.random_tendencies(rng, 0.2),
    )
    leader.is_player = True
    leader.health = 85
    leader.means.set("hands", STATIONS["leader"].hands)
    nation.leader_id = leader.id
    nation.leading_family = leader.family_name
    state.player_id = leader.id
    mother = create_character(
        state, "keeper", home.id, state.year - 44, gender="female", family_name=leader.family_name
    )
    father = create_spouse(state, mother)
    father.birth_year = state.year - 47
    for parent in (mother, father):
        parent.children.append(leader.id)
    leader.mother_id, leader.father_id = mother.id, father.id
    die(state, mother, "a winter fever")
    ensure_elders(state)

    state.log.append(
        f"[b]Year {state.year}[/b]  Your mother, who led the {nation.name}, died this winter. "
        f"The people have turned to you, {leader.full_name}, though you are only twenty."
    )
    begin_year(state)
    return state


# --- the year ------------------------------------------------------------------


@dataclass
class Option:
    """Something the player could give a slot of attention to this year."""

    key: str  # plan entry: "event:<i>", "p:<project id>", "new:<kind>:<target>" or a deed id
    kind: str  # "obligation", "continue", "project" or "deed"
    name: str
    text: str
    cost: dict  # per year
    pull: float  # hidden affinity; the UI uses it only to order and tint
    tags: tuple
    scope: str  # "people" or "own": what the cost is drawn from
    years: int = 1
    blurb: str = ""
    action: object = None
    project: object = None  # a ProjectOption (new) or Project (continue)
    event_index: int | None = None


@dataclass
class YearReport:
    year: int
    lines: list[str] = field(default_factory=list)
    interrupts: list[str] = field(default_factory=list)
    life_ended: bool = False


def _scope(state, char, item):
    return "people" if budget_for(state, char, item) is state.nation.stores else "own"


def _new_key(option):
    return f"new:{option.definition.id}:{option.target or ''}"


def options(state):
    """Everything the player can choose this year: what's expected first, then what they're
    already doing, then new undertakings and this year's deeds, by inclination."""
    player = state.player
    out = []
    for i, event in enumerate(state.events):
        if event.obligation:
            action = ACTIONS[event.obligation]
            out.append(
                Option(
                    obligation_key(i),
                    "obligation",
                    action.name,
                    action.text,
                    effective_cost(state, player, action),
                    tendencies.affinity(player.tendencies, action.tags),
                    action.tags,
                    _scope(state, player, action),
                    blurb=event.text,
                    action=action,
                    event_index=i,
                )
            )
    for project in sorted(state.projects_of(player.id), key=lambda p: p.slot):
        d = projects.PROJECTS[project.kind]
        out.append(
            Option(
                f"p:{project.id}",
                "continue",
                projects.display_name(state, project),
                d.text,
                projects.yearly_cost(state, project),
                tendencies.affinity(player.tendencies, d.tags),
                d.tags,
                _scope(state, player, d),
                years=max(1, project.years_needed - project.years_done),
                project=project,
            )
        )
    new = [
        Option(
            _new_key(o),
            "project",
            o.name,
            o.definition.text,
            o.cost,
            tendencies.affinity(player.tendencies, o.definition.tags),
            o.definition.tags,
            _scope(state, player, o.definition),
            years=o.years,
            project=o,
        )
        for o in projects.options_for(state, player)
    ]
    obligated = {o.action.id for o in out if o.action}
    deeds = [
        Option(
            a.id,
            "deed",
            a.name,
            a.text,
            effective_cost(state, player, a),
            tendencies.affinity(player.tendencies, a.tags),
            a.tags,
            _scope(state, player, a),
            action=a,
        )
        for a in actions_for(state, player)
        if a.id not in obligated
    ]
    new.sort(key=lambda o: -o.pull)
    deeds.sort(key=lambda o: -o.pull)
    return out + new + deeds


def option_for(state, key):
    return next((o for o in options(state) if o.key == key), None)


def remaining_budget(state, excluding_slot=None):
    """Common stores and the player's own means left after the other planned slots."""
    stores = state.nation.stores.copy()
    own = state.player.means.copy()
    for i, key in enumerate(state.plan):
        if key is None or i == excluding_slot:
            continue
        opt = option_for(state, key)
        if opt is not None:
            (stores if opt.scope == "people" else own).spend(opt.cost)
    return stores, own


def affordable(state, opt, slot):
    stores, own = remaining_budget(state, excluding_slot=slot)
    return (stores if opt.scope == "people" else own).can_afford(opt.cost)


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
    for project in sorted(state.projects_of(state.player_id), key=lambda p: p.slot):
        slot = project.slot if state.plan[project.slot] is None else state.plan.index(None)
        project.slot = slot
        state.plan[slot] = f"p:{project.id}"
    # habit fills empty slots with what this character is drawn to
    state.defaults = []
    for opt in options(state):
        if None not in state.plan:
            break
        if opt.kind in ("obligation", "continue") or opt.pull < tendencies.DEFAULT_THRESHOLD:
            continue
        if choose(state, state.plan.index(None), opt.key):
            state.defaults.append(opt.key)


def _tags_for_key(key):
    if key.startswith("new:"):
        return projects.PROJECTS[key.split(":")[1]].tags
    action = ACTIONS.get(key)
    return action.tags if action else ()


def end_year(state):
    """Carry out the plan and advance the world one year."""
    rng = state.rng()
    player = state.player
    report = YearReport(state.year)
    lines, interrupts = report.lines, report.interrupts
    karma = 0.0

    chosen = [(slot, option_for(state, key)) for slot, key in enumerate(state.plan) if key]
    worked = set()
    for slot, opt in chosen:
        if opt is None:
            continue
        if opt.kind in ("deed", "obligation"):
            event = state.events[opt.event_index] if opt.kind == "obligation" else None
            budget_for(state, player, opt.action).spend(opt.cost)
            result = opt.action.effect(Ctx(state, player, rng, event))
            lines.append(f"{opt.action.name}: {result}")
            karma += opt.action.karma
            tendencies.strengthen(player.tendencies, opt.tags)
            continue
        if opt.kind == "project":
            project = projects.start(state, player, opt.project, slot)
            lines.append(f"You took on something new: {_lower_first(opt.name)}.")
        else:
            project = opt.project
        worked.add(project.id)
        name = projects.display_name(state, project)
        line, outcome = projects.work_year(state, project, rng)
        if outcome != "stalled":
            karma += projects.PROJECTS[project.kind].karma
            tendencies.strengthen(player.tendencies, opt.tags)
        if line:
            lines.append(line)
        if outcome == "done":
            interrupts.append(f"Finished: {name}.")
        elif outcome == "stalled":
            interrupts.append(f"Stalled for want of means: {name}.")
    for project in state.projects_of(player.id):
        if project.id not in worked:
            projects.abandon(state, project)
            tendencies.weaken(player.tendencies, projects.PROJECTS[project.kind].tags)
            name = _lower_first(projects.display_name(state, project))
            lines.append(f"You set aside: {name}.")
    for key in state.defaults:
        if key not in state.plan:
            tendencies.weaken(player.tendencies, _tags_for_key(key))

    notes, obligation_karma = resolve_events(state, state.plan)
    lines += notes
    karma += obligation_karma
    state.soul.karma = tendencies.clamp(state.soul.karma + KARMA_SCALE * karma)

    if state.pending_choice:
        # nobody chose, so the people's own leanings decide
        lines.append(_learn(state, state.pending_choice, None, rng))
        state.pending_choice = None

    was_leader = player.station == "leader"
    _world_year(state, (), lines, interrupts)
    if player.station == "leader" and not was_leader:
        interrupts.append("The people have turned to you to lead them.")

    cause = age_and_health(state, player, rng)
    if cause:
        _end_life(state, cause)
        report.life_ended = True
        lines.append(f"[b]{player.full_name} died of {cause}, aged {player.age(state.year)}.[/b]")
        note = succeed(state)
        if note:
            lines.append(note)
    else:
        ensure_elders(state)

    _log(state, state.year, lines)
    state.year += 1
    if report.life_ended:
        interrupts.insert(0, "A life has ended.")
    else:
        begin_year(state)
        if any(e.obligation for e in state.events):
            interrupts.append("Something is expected of you.")
        if state.pending_choice:
            name = discoveries.DISCOVERIES[state.pending_choice].name
            interrupts.append(f"A choice must be made: {name.lower()}.")
    return report


def _lower_first(text):
    return text[:1].lower() + text[1:]


def _world_year(state, protect, lines, interrupts):
    """Everything that happens whatever the player does."""
    rng = state.rng()
    player = state.player
    near = {player.spouse_id, player.mother_id, player.father_id, *player.children}
    alive_before = {cid for cid in near if cid and state.character(cid).alive}
    kids_before = len(player.children)

    lines += npc_year(state, protect)
    lines += economy_year(state)
    lines += households_year(state)
    discoveries.yearly_insight(state, rng)
    _settle_discoveries(state, lines, interrupts, rng)
    notes, met = neighbours_year(state, rng)
    lines += notes
    interrupts += met
    lines += yearly_lifecycle(state, protect)
    note = succeed(state)
    if note:
        lines.append(note)

    lost = [state.character(cid) for cid in alive_before if not state.character(cid).alive]
    if lost and not protect:
        interrupts.append(f"{lost[0].name} has died.")
    if len(player.children) > kids_before and not protect:
        interrupts.append("A child has been born to you.")


def _player_led(state, did):
    return any(p.kind == "pursue" and p.target == did for p in state.projects_of(state.player_id))


def _settle_discoveries(state, lines, interrupts, rng):
    """Ideas with enough insight become things the people know."""
    player = state.player
    for d in discoveries.ripe(state):
        choosing = d.forms and (
            _player_led(state, d.id) or (player.station == "leader" and d.domain == "kin")
        )
        if choosing:
            if state.pending_choice is None:
                state.pending_choice = d.id
            continue
        lines.append(_learn(state, d.id, None, rng))
        if _player_led(state, d.id) or player.station == "leader":
            interrupts.append(f"Something new is understood: {d.name.lower()}.")
    # whoever was working at something now known can stop
    for project in list(state.projects.values()):
        if project.kind == "pursue" and project.target in state.nation.known:
            if project.leader_id == state.player_id:
                interrupts.append(f"Finished: {projects.display_name(state, project)}.")
            projects.abandon(state, project)


def _learn(state, did, form_id, rng):
    d = discoveries.DISCOVERIES[did]
    if d.forms and form_id is None:
        form_id = discoveries.pick_form(state, d, rng)
    return "The people have come to understand " + discoveries.learn(state, did, form_id or "")


def choose_form(state, form_id):
    """The player decides what shape a newly understood custom takes."""
    did = state.pending_choice
    d = discoveries.DISCOVERIES[did]
    form = d.form(form_id)
    player = state.player
    tendencies.strengthen(player.tendencies, form.tags)
    state.soul.karma = tendencies.clamp(
        state.soul.karma + KARMA_SCALE * FORM_KARMA * tendencies.tag_karma(form.tags)
    )
    line = "You shaped what the people came to understand: " + discoveries.learn(
        state, did, form_id
    )
    state.log.append(f"[b]Year {state.year}[/b]  {line}")
    state.pending_choice = None
    for project in list(state.projects.values()):
        if project.kind == "pursue" and project.target == did:
            projects.abandon(state, project)
    begin_year(state)
    return line


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
            "settlement": (state.settlement(player.settlement_id) or state.seat).name,
        }
    )
    for project in state.projects_of(player.id):
        projects.abandon(state, project)
    state.pending_choice = None
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
        if c.gender != "female" or c.is_player or not (17 <= c.age(state.year) <= 40):
            continue
        husband = state.character(c.spouse_id)
        if not husband or not husband.alive:
            continue
        if station == "leader":
            if state.nation.leader_id in (c.id, husband.id):
                out.append((c, husband))
        elif husband.station == station:
            out.append((c, husband))
    return out


def _new_parents(state, station, karma, rng):
    home = rng.choice(list(state.settlements.values()))
    if station == "leader":
        home = state.seat
    father = create_character(
        state,
        station if station != "leader" else "hunter",
        home.id,
        state.year - rng.randint(20, 36),
        gender="male",
    )
    mother = create_spouse(state, father)
    mother.birth_year = state.year - rng.randint(18, 32)
    for parent in (father, mother):
        for t, v in tendencies.VALENCE.items():
            parent.tendencies[t] = tendencies.clamp(parent.tendencies.get(t, 0) + 0.3 * karma * v)
    return mother, father


def begin_next_life(state):
    """Begin a new life among the same people and fast-forward through childhood.

    Returns lines describing the birth and the years of childhood.
    """
    rng = state.rng()
    soul = state.soul
    karma = soul.karma
    weights = rebirth_weights(state.nation)
    station = rng.choices(list(weights), list(weights.values()))[0]

    candidates = _candidate_mothers(state, station)
    if candidates:
        # better karma, kinder parents
        w = [math.exp(2 * karma * (_wholesomeness(m) + _wholesomeness(f))) for m, f in candidates]
        mother, father = rng.choices(candidates, w)[0]
    else:
        mother, father = _new_parents(state, station, karma, rng)

    child = create_character(
        state,
        station if station != "leader" else child_role(state, father, rng),
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

    home = state.settlement(child.settlement_id) or state.seat
    nation = state.nation
    parent_role = station_title(father, nation).lower()
    lines = [
        f"[b]Year {state.year}[/b]  {child.full_name} was born at {home.name} to "
        f"{mother.full_name} and {father.full_name}, {parent_role}."
    ]
    if nation.leader_id in (mother.id, father.id):
        lines[0] = lines[0].rsplit(",", 1)[0] + ", who lead the people."

    # childhood passes without the player's hand
    for _ in range(ADULT_AGE):
        state.modifiers = {}
        notable = [
            e.text
            for e in generate_events(state, child, whole_people_only=True)
            if e.kind in ("lean_year", "sickness", "flood", "raid")
        ]
        _world_year(state, {child.id}, notable, [])
        notable = [n for n in notable if _childhood_notable(n)]
        if notable:
            _log(state, state.year, notable)
            lines.append(f"[b]Year {state.year}[/b]  " + "  ".join(notable))
        state.year += 1

    child.means = Budget(dict(STATIONS[child.station].start))
    child.means.add(STATIONS[child.station].start, child.fortune - 1)
    child.means.set("hands", STATIONS[child.station].hands)
    child.means.clamp_nonnegative()
    ensure_elders(state)
    lines.append(
        f"[b]Year {state.year}[/b]  {child.name} is {ADULT_AGE} and must find their own way, "
        f"as a {station_title(child, nation).lower()}."
    )
    state.log.append(lines[-1])
    begin_year(state)
    return lines


def _childhood_notable(line):
    """Childhood is told in broad strokes: who died, who led, what was learned, who came."""
    return not line.startswith(("Hunger in", "The common stores", "The camps came"))


def life_summary(state):
    """The most recent finished life, for the end-of-life screen."""
    return state.soul.lives[-1] if state.soul.lives else None
