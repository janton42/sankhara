"""The game loop: a small people at the start of everything, played a year at a time as
the current character; when a life ends, the next begins somewhere else among the
same people.

The UI only talks to this module: `new_game`, `options`, `choose`, `affordable`, `unmet`,
`remaining_budget`, `end_year`, `choose_form`, `begin_next_life` and `threads`.
"""

import math
from dataclasses import dataclass, field

from sankhara.constants.config import CULTURE_GROUPS
from sankhara.core.game_engine import new_seed
from sankhara.entities.namer import make_family_name
from sankhara.sim import discoveries, projects, tendencies
from sankhara.sim.actions import ACTIONS, Ctx, budget_for, cares_for, effective_cost
from sankhara.sim.events import answer_key, generate_events, resolve_events, unmet
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
    leadership_year,
    make_leader,
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
ATTENDED_KARMA = 0.02  # a year the player stepped through themselves
DRIFTED_KARMA = -0.02  # a year let slip by with nothing taken up
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

    # the first life: someone the people have lately come to look to
    leader = create_character(
        state,
        "hunter",
        home.id,
        state.year - rng.randint(22, 30),
        tendencies=tendencies.random_tendencies(rng, 0.2),
    )
    leader.is_player = True
    leader.health = 85
    leader.death_age = max(leader.death_age, leader.age(state.year) + 25)
    leader.means.set("regard", 25)
    state.player_id = leader.id
    make_leader(state, leader)
    leader.means.set("hands", STATIONS["leader"].hands)
    ensure_elders(state)
    state.log.append(f"[b]Year {state.year}[/b]  " + _how_you_came_to_lead(state, leader, rng))
    begin_year(state)
    return state


def _how_you_came_to_lead(state, leader, rng):
    """Why the people look to the first life: a deed, never a birthright."""
    nation = state.nation
    old = create_character(state, "keeper", state.seat.id, state.year - rng.randint(55, 68))
    elders = [c for c in state.living() if c.is_elder]
    a, b = rng.sample(elders, 2)
    stories = [
        (
            True,
            f"{old.full_name}, who led the {nation.name} through many winters, has grown too "
            f"frail to walk with the hunters. At the spring gathering the people turned to "
            f"you, {leader.full_name}, who brought the hunters home through last year's snows.",
        ),
        (
            False,
            f"{old.full_name}, who led the {nation.name}, was killed by a bear in the autumn. "
            f"You drove the beast off and carried {old.name} home, and since then the people "
            f"have looked to you, {leader.full_name}, to lead them.",
        ),
        (
            True,
            f"The {nation.name} quarrelled all winter, the families of {a.family_name} and "
            f"{b.family_name} at each other's fires. When you, {leader.full_name}, settled "
            f"it, {old.full_name} gave way and the people turned to you to lead them.",
        ),
        (
            True,
            f"When the springs dried last summer, you found water beyond the ridge and led the "
            f"people to it. {old.full_name}, who had led them, gave way gladly, and the "
            f"{nation.name} now look to you, {leader.full_name}.",
        ),
    ]
    lives, text = rng.choice(stories)
    if lives:
        old.is_elder = True
        old.means.set("regard", 20)
    else:
        die(state, old, "a bear's mauling")
    return text


# --- the year ------------------------------------------------------------------


@dataclass
class Option:
    """Something the player could give a slot of attention to this year."""

    key: str  # plan entry: "a:<matter>:<action>", "p:<id>", "join:<id>", "rally:<id>",
    # "new:<kind>:<target>" or a care's action id
    kind: str  # "answer", "continue", "join", "rally", "project", "personal" or "care"
    name: str
    text: str
    cost: dict  # per year
    pull: float  # hidden affinity; the UI uses it only to order and tint
    tags: tuple
    scope: str  # "people" or "own": what the cost is drawn from
    years: int = 1
    blurb: str = ""
    action: object = None
    project: object = None  # a ProjectOption (new) or Project (continue, join, rally)
    event_index: int | None = None  # the matter an answer meets
    expected: bool = False  # an answer to a matter expected of the player
    thread: bool = False  # something an earlier life of the player's worked on

    @property
    def group(self):
        """Where the chooser shows it: "works", "matters" or "own"."""
        if self.kind == "answer":
            return "matters"
        if self.kind in ("personal", "care"):
            return "own"
        if self.kind == "continue" and not self.project.common:
            return "own"
        return "works"


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


def _pull(player, tags):
    return tendencies.affinity(player.tendencies, tags)


def _project_text(state, project):
    leader = state.character(project.leader_id)
    helpers = len(project.helpers)
    who = (
        f"led by {leader.full_name}"
        if leader
        else f"begun by {project.started_by}, left unfinished"
    )
    if leader and project.started_by != leader.full_name:
        who += f", begun by {project.started_by}"
    if helpers:
        who += f", {helpers} helping"
    return f"{who}  ·  {projects.progress_word(projects.progress(state, project))}"


def committed(state):
    """The projects the player is working on, led or helped, with their slots."""
    out = []
    for pid, slot in state.commitments.items():
        project = state.projects.get(pid)
        if project and state.player_id in (project.leader_id, *project.helpers):
            out.append((slot, project))
    return sorted(out, key=lambda x: x[0])


def options(state):
    """Everything the player can give a slot to this year, in three groups: the matters at
    hand (expected ones first), the people's works (what they are working on, could join,
    call others to or begin) and their own (personal undertakings and lasting cares)."""
    player = state.player
    works, own = [], []
    for _, project in committed(state):
        d = projects.PROJECTS[project.kind]
        leading = project.leader_id == player.id
        (works if project.common else own).append(
            Option(
                f"p:{project.id}",
                "continue",
                projects.display_name(state, project),
                d.text if leading else _project_text(state, project),
                projects.yearly_cost(state, project)
                if leading
                else projects.help_cost(state, player, project),
                _pull(player, d.tags),
                d.tags,
                _scope(state, player, d) if leading else "own",
                years=projects.years_left(state, project),
                project=project,
            )
        )
    joins = []
    for project in projects.joinable(state, player):
        d = projects.PROJECTS[project.kind]
        taking_up = project.leader_id is None
        joins.append(
            Option(
                f"join:{project.id}",
                "join",
                ("Take up: " if taking_up else "Help with: ")
                + projects.display_name(state, project),
                _project_text(state, project),
                effective_cost(state, player, d)
                if taking_up
                else projects.help_cost(state, player, project),
                _pull(player, d.tags),
                d.tags,
                _scope(state, player, d) if taking_up else "own",
                years=projects.years_left(state, project),
                project=project,
                thread=bool(project.worked_by),
            )
        )
    joins.sort(key=lambda o: (not o.thread, -o.pull))
    rallies = [
        Option(
            f"rally:{project.id}",
            "rally",
            f"Call others to {_lower_first(projects.display_name(state, project))}",
            "Go from fire to fire asking people to lend a hand this year and next.",
            projects.rally_cost(state, player),
            _pull(player, projects.RALLY_TAGS),
            projects.RALLY_TAGS,
            "own",
            project=project,
        )
        for _, project in committed(state)
        if project.common
    ]
    new, personal = [], []
    offered = set()
    for o in projects.options_for(state, player):
        d = o.definition
        if d.id != "pursue" and d.id in offered:
            continue  # one of each kind of work, where it is needed most; ideas each their own
        offered.add(d.id)
        (new if d.common else personal).append(
            Option(
                _new_key(o),
                "project" if d.common else "personal",
                o.name,
                d.text,
                o.cost,
                _pull(player, d.tags),
                d.tags,
                _scope(state, player, d),
                years=o.years,
                project=o,
            )
        )
    new.sort(key=lambda o: -o.pull)
    personal.sort(key=lambda o: -o.pull)

    matters = []
    order = sorted(range(len(state.events)), key=lambda i: not state.events[i].expected)
    for i in order:
        event = state.events[i]
        answers = [ACTIONS[a] for a in event.answers]
        answers.sort(key=lambda a: -_pull(player, a.tags))
        for action in answers:
            matters.append(
                Option(
                    answer_key(event, action.id),
                    "answer",
                    action.label(event),
                    action.text,
                    effective_cost(state, player, action),
                    _pull(player, action.tags),
                    action.tags,
                    _scope(state, player, action),
                    blurb=event.text,
                    action=action,
                    event_index=i,
                    expected=event.expected,
                )
            )
    cares = [
        Option(
            a.id,
            "care",
            a.name,
            a.text,
            effective_cost(state, player, a),
            _pull(player, a.tags),
            a.tags,
            _scope(state, player, a),
            action=a,
        )
        for a in cares_for(state, player)
    ]
    cares.sort(key=lambda o: -o.pull)
    return matters + works + joins + rallies + new + own + personal + cares


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


def begin_year(state, carry=()):
    """A new year. What the player is working on keeps its slot, cares they chose last year
    are kept up if they still can be, and so is an answer to a matter that is still at hand;
    nothing else is chosen for them.

    Returns the names of deeds that could not be kept up.
    """
    state.modifiers = {}
    state.events = generate_events(state, state.player)
    keep = [key if key and (key in ACTIONS or key.startswith("a:")) else None for key in carry]
    return replan(state, keep)


def replan(state, keys):
    """Lay out the plan again: commitments in their slots, then whichever of `keys` still
    make sense. Returns the names of deeds dropped."""
    state.plan = [None] * ACTION_SLOTS
    held = committed(state)
    state.commitments = {}
    for slot, project in held:
        slot = slot if state.plan[slot] is None else state.plan.index(None)
        state.commitments[str(project.id)] = slot
        state.plan[slot] = f"p:{project.id}"
    dropped = []
    for slot, key in enumerate(keys):
        if not key or key.startswith("p:") or state.plan[slot] is not None:
            continue
        if not choose(state, slot, key) and key in ACTIONS:
            dropped.append(ACTIONS[key].name)
    return dropped


def _work_player_project(state, project, lines, interrupts, rng):
    """The player leads this project: a year's work. Returns the karma it carries."""
    name = projects.display_name(state, project)
    line, outcome = projects.work_year(state, project, rng)
    if line:
        lines.append(line)
    if outcome == "stalled":
        interrupts.append(f"Stalled for want of means: {name}.")
        return 0.0
    if outcome == "done":
        interrupts.append(f"Finished: {name}.")
    return projects.PROJECTS[project.kind].karma


def end_year(state, attended=True):
    """Carry out the plan and advance the world one year. `attended` is False when the
    player let the year pass rather than stepping through it."""
    if state.life_over:
        raise ValueError("this life is over; begin the next one first")
    rng = state.rng()
    player = state.player
    report = YearReport(state.year)
    lines, interrupts = report.lines, report.interrupts
    karma = 0.0
    carry = list(state.plan)
    was_leader = player.station == "leader"

    chosen = [(slot, option_for(state, key)) for slot, key in enumerate(state.plan) if key]
    kept = set()
    for slot, opt in chosen:
        if opt is None:
            continue
        if opt.kind in ("care", "answer"):
            event = state.events[opt.event_index] if opt.kind == "answer" else None
            budget_for(state, player, opt.action).spend(opt.cost)
            result = opt.action.effect(Ctx(state, player, rng, event))
            lines.append(f"{opt.name}: {result}")
            karma += opt.action.karma
            tendencies.strengthen(player.tendencies, opt.tags)
            continue
        if opt.kind == "rally":
            player.means.spend(opt.cost)
            lines.append(projects.rally(state, player, opt.project))
            tendencies.strengthen(player.tendencies, opt.tags)
            continue
        if opt.kind in ("project", "personal"):
            project = projects.start(state, player, opt.project)
            lines.append(f"You took on something new: {_lower_first(opt.name)}.")
        elif opt.kind == "join":
            project = opt.project
            lines.append(projects.join(state, player, project))
        else:
            project = opt.project
        state.commitments[str(project.id)] = slot
        kept.add(str(project.id))
        tendencies.strengthen(player.tendencies, opt.tags)
        if project.leader_id == player.id:
            karma += _work_player_project(state, project, lines, interrupts, rng)
        else:
            karma += projects.PROJECTS[project.kind].karma  # worked by its leader, with you
    for pid in [p for p in state.commitments if p not in kept]:
        project = state.projects.get(pid)
        del state.commitments[pid]
        if project is None:
            continue
        tendencies.weaken(player.tendencies, projects.PROJECTS[project.kind].tags)
        name = _lower_first(projects.display_name(state, project))
        lines.append(f"You set aside {name}.")
        note = projects.leave(state, player, project)
        if note:
            lines.append(note)
    if attended:
        karma += ATTENDED_KARMA
    elif not any(state.plan):
        karma += DRIFTED_KARMA

    notes, matter_karma = resolve_events(state, state.plan)
    lines += notes
    karma += matter_karma
    state.soul.karma = tendencies.clamp(state.soul.karma + KARMA_SCALE * karma)

    if state.pending_choice:
        # nobody chose, so the people's own leanings decide
        lines.append(_learn(state, state.pending_choice, None, rng))
        state.pending_choice = None
        state.pending_mode = ""

    _world_year(state, (), lines, interrupts)
    if player.station == "leader" and not was_leader:
        interrupts.append("The people have turned to you to lead them.")
    elif was_leader and player.station != "leader" and player.alive:
        leader = state.leader
        interrupts.append(f"The people now look to {leader.full_name} to lead them.")

    cause = age_and_health(state, player, rng)
    if cause:
        _end_life(state, cause, lines)
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
        dropped = begin_year(state, carry)
        if dropped:
            interrupts.append(f"You could not keep up: {', '.join(dropped).lower()}.")
        if unmet(state):
            interrupts.append("Something is expected of you.")
        if state.pending_choice:
            name = discoveries.DISCOVERIES[state.pending_choice].name.lower()
            if state.pending_mode == "decide":
                interrupts.append(f"A choice must be made: {name}.")
            else:
                interrupts.append(f"The people are deciding: {name}.")
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
    _settle_discoveries(state, lines, interrupts, rng, protect)
    notes, met = neighbours_year(state, rng)
    lines += notes
    interrupts += met
    lines += yearly_lifecycle(state, protect)
    for note in (succeed(state), leadership_year(state)):
        if note:
            lines.append(note)
    _orphaned_works(state, lines)
    if not protect:
        interrupts += projects.player_notes(state)
    else:
        projects.player_notes(state)

    lost = [state.character(cid) for cid in alive_before if not state.character(cid).alive]
    if lost and not protect:
        interrupts.append(f"{lost[0].name} has died.")
    if len(player.children) > kids_before and not protect:
        interrupts.append("A child has been born to you.")


def _orphaned_works(state, lines):
    """The people's works whose leader has died pass to someone else."""
    for project in list(state.projects.values()):
        leader = state.character(project.leader_id)
        if project.leader_id is not None and (leader is None or not leader.alive):
            line = projects.pass_on(state, project)
            if line and project.worked_by:
                lines.append(line)


def _idea_workers(state, did):
    """Projects working at this idea: (led by the player, helped by the player, names)."""
    led = helped = False
    names = []
    for p in state.projects.values():
        if p.kind == "pursue" and p.target == did:
            led = led or p.leader_id == state.player_id
            helped = helped or state.player_id in p.helpers
            names += p.worked_by
    return led, helped, names


def _settle_discoveries(state, lines, interrupts, rng, protect=()):
    """Ideas with enough insight become things the people know. A custom with several
    possible forms is decided by the player if they worked it out or lead (and it's a
    matter of custom); otherwise the player can speak for one, unless still a child."""
    player = state.player
    for d in discoveries.ripe(state):
        led, helped, names = _idea_workers(state, d.id)
        if d.forms and player.id not in protect and not state.life_over:
            if state.pending_choice is None:
                decides = led or (player.station == "leader" and d.domain == "kin")
                state.pending_choice = d.id
                state.pending_mode = "decide" if decides else "voice"
            if state.pending_choice == d.id:
                continue
        lines.append(_learn(state, d.id, None, rng))
        if names:
            projects.record(state, f"The people came to understand {d.name.lower()}.", names)
        if led or helped or player.station == "leader":
            interrupts.append(f"Something new is understood: {d.name.lower()}.")
    # whoever was working at something now known can stop
    for project in list(state.projects.values()):
        if project.kind == "pursue" and project.target in state.nation.known:
            if state.player_id in (project.leader_id, *project.helpers):
                interrupts.append(f"Finished: {projects.display_name(state, project)}.")
            projects.abandon(state, project)


def _learn(state, did, form_id, rng):
    d = discoveries.DISCOVERIES[did]
    if d.forms and form_id is None:
        form_id = discoveries.pick_form(state, d, rng)
    return "The people have come to understand " + discoveries.learn(state, did, form_id or "")


VOICE_WEIGHT = 25  # regard at which the player's voice doubles a form's chances


def choose_form(state, form_id):
    """The player decides, or speaks for, the shape a newly understood custom takes."""
    did = state.pending_choice
    d = discoveries.DISCOVERIES[did]
    form = d.form(form_id)
    player = state.player
    rng = state.rng()
    tendencies.strengthen(player.tendencies, form.tags)
    state.soul.karma = tendencies.clamp(
        state.soul.karma + KARMA_SCALE * FORM_KARMA * tendencies.tag_karma(form.tags)
    )
    _, _, names = _idea_workers(state, did)
    if state.pending_mode == "decide":
        text = discoveries.learn(state, did, form_id)
        line = "You shaped what the people came to understand: " + text
        projects.record(
            state, f"{d.name}: {form.name.lower()}, as you decided.", [player.full_name]
        )
    else:
        voice = 1 + player.means.get("regard") / VOICE_WEIGHT
        weights = [
            math.exp(4 * discoveries.people_lean(state, f.tags)) * (voice if f.id == form_id else 1)
            for f in d.forms
        ]
        settled = rng.choices(d.forms, weights)[0]
        text = discoveries.learn(state, did, settled.id)
        if settled.id == form_id:
            line = "The people settled it as you had urged: " + text
            projects.record(
                state, f"{d.name}: {settled.name.lower()}, as you urged.", [player.full_name]
            )
        else:
            line = f"You spoke for {form.name.lower()}, but the people settled otherwise: " + text
    if names:
        projects.record(state, f"The people came to understand {d.name.lower()}.", names)
    state.log.append(f"[b]Year {state.year}[/b]  {line}")
    state.pending_choice = None
    state.pending_mode = ""
    for project in list(state.projects.values()):
        if project.kind == "pursue" and project.target == did:
            projects.abandon(state, project)
    replan(state, state.plan)
    return line


def _log(state, year, lines):
    body = "  ".join(lines) if lines else "A quiet year."
    state.log.append(f"[b]Year {year}[/b]  {body}")
    del state.log[:-LOG_LIMIT]


def _end_life(state, cause, lines):
    player = state.player
    state.soul.tendencies = dict(player.tendencies)
    for pid in list(state.commitments):
        project = state.projects.get(pid)
        if project is not None:
            line = projects.leave(state, player, project)
            if line:
                lines.append(line)
    state.commitments = {}
    state.soul.lives.append(
        {
            "name": player.full_name,
            "station": station_title(player, state.nation),
            "born": player.birth_year,
            "died": state.year,
            "age": player.age(state.year),
            "cause": cause,
            "settlement": (state.settlement(player.settlement_id) or state.seat).name,
            "legacy": [e["text"] for e in state.legacy if player.full_name in e["names"]],
        }
    )
    state.pending_choice = None
    state.pending_mode = ""
    die(state, player, cause)
    state.life_over = True


def threads(state):
    """Works earlier lives of the player's had a hand in that are still unfinished."""
    out = []
    for project in state.projects.values():
        if project.worked_by and state.player_id not in (project.leader_id, *project.helpers):
            out.append(project)
    return out


def thread_lines(state):
    lines = []
    for project in threads(state):
        name = projects.display_name(state, project)
        leader = state.character(project.leader_id)
        carried = (
            f"carried on by {leader.full_name}" if leader else "waiting for someone to take it up"
        )
        lines.append(
            f"{name}, worked on by {', '.join(project.worked_by)}, is "
            f"{projects.progress_word(projects.progress(state, project))}, {carried}."
        )
    return lines


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
    legacy_before = len(state.legacy)
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
    # the thread from before: what was finished meanwhile, and what still waits
    for entry in state.legacy[legacy_before:]:
        lines.append(f"While {child.name} grew up: {entry['text']}")
    lines += [f"Still unfinished: {line}" for line in thread_lines(state)]
    begin_year(state)
    return lines


def _childhood_notable(line):
    """Childhood is told in broad strokes: who died, who led, what was learned, who came."""
    return not line.startswith(("Hunger in", "The common stores", "The camps came"))


def life_summary(state):
    """The most recent finished life, for the end-of-life screen."""
    return state.soul.lives[-1] if state.soul.lives else None
