"""Undertakings that take several years of attention.

A project holds one attention slot year after year until it is finished, set
aside or stalls for want of means. It is paid for every year it is worked, and
its inclination tags and karma count each year too: carrying something on is a
choice made again every year.

Most are the people's works (`common`): anyone can start one with their own
means, others can help (each helper's attention adds to the work), anyone can
call more people to it, and it outlives whoever leads it. When a leader dies or
sets it aside it passes to a helper, the people's leader or an elder, or lies
unfinished until someone takes it up. That is how a hunter can shape the people,
and how what one life begins can be carried on by the next.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from sankhara.sim import discoveries, tendencies
from sankhara.sim.actions import Ctx, budget_for, effective_cost, heal
from sankhara.sim.nation import WORK_CAPS, advance, capacity
from sankhara.sim.state import Project, Settlement
from sankhara.sim.stations import ADULT_AGE, STATIONS
from sankhara.sim.world import direction, forage_value, game_map, place_name, tile
from sankhara.world.hexgrid import distance, neighbors

PURSUE_RATE = 7.0  # insight a year from someone working at an idea
NPC_PURSUE_RATE = 0.6  # NPCs are not modelled as carefully; they work at ideas more slowly
EXPLORE_TILES = 3
HELP_COST = {"hands": 2}  # what helping with someone else's work costs a year
HELPER_EFFORT = 0.5  # a helper's work, relative to the one leading it
FIT_EFFORT = 0.8  # ...when it is their kind of work
SUPPORT_EFFORT = 0.25  # work from each point of support among the people at large
SUPPORT_FADE = 0.8  # support fades unless someone keeps calling people to it
RALLY_COST = {"regard": 5}
RALLY_TAGS = ("ambitious", "caring")
LEGACY_LIMIT = 200


@dataclass(frozen=True)
class ProjectDef:
    id: str
    name: str  # may contain {target}
    text: str
    stations: tuple  # empty = anyone
    tags: tuple
    karma: float  # hidden, per year worked
    years: int
    cost: dict  # per year
    work: Callable | None = field(default=None, repr=False)  # (ctx, project) -> str | None
    finish: Callable | None = field(default=None, repr=False)  # (ctx, project) -> str
    targets: Callable | None = field(default=None, repr=False)  # (state, char) -> [(id, label)]
    requires: Callable | None = field(default=None, repr=False)  # (state, char) -> bool
    scope: str = "own"  # "people" draws on the common stores when the leader leads it
    common: bool = True  # the people's work, which others can join and which outlives its leader


def _camp(state, project):
    return state.settlement(project.target) or state.seat


def _neighbour(state, project):
    return state.neighbour(project.target)


# --- working at an idea --------------------------------------------------------


def _pursue_targets(state, char):
    domains = STATIONS[char.station].domains
    return [
        (d.id, discoveries.QUESTIONS.get(d.id, d.name.lower()))
        for d in discoveries.stirring(state)
        if d.domain in domains
    ]


def pursue_rate(state, char):
    base = PURSUE_RATE if char.is_player else NPC_PURSUE_RATE
    lean = tendencies.affinity(char.tendencies, ("studious",))
    return base * (1 + 0.5 * lean) * (0.8 + state.nation.lore / 100)


def _pursue_work(ctx, project):
    if project.target not in ctx.nation.known:
        discoveries.add_insight(ctx.state, project.target, pursue_rate(ctx.state, ctx.char))
    return None


def _pursue_years(state, char, target):
    d = discoveries.DISCOVERIES[target]
    left = max(0.0, d.cost - state.nation.insight.get(target, 0))
    return max(1, math.ceil(left / pursue_rate(state, char)))


# --- the people's works ------------------------------------------------------


def _new_camp_sites(state, char):
    crowded = [
        s
        for s in state.settlements.values()
        if s.population > 80 and s.population > 0.7 * capacity(state, s)
    ]
    if not crowded:
        return []  # nobody needs to move yet
    camps = [(s.col, s.row) for s in state.settlements.values()]
    sites = [
        tile(state, c, r)
        for c, r in state.nation.territory
        if all(distance((c, r), camp) >= 2 for camp in camps)
    ]
    sites = sorted((t for t in sites if t and forage_value(t) > 0.3), key=forage_value)
    seat = (state.seat.col, state.seat.row)
    return [
        (f"{t['q']},{t['r']}", f"{t['biome'].lower()} to the {direction(seat, (t['q'], t['r']))}")
        for t in reversed(sites[-3:])
    ]


def _new_camp_finish(ctx, project):
    state = ctx.state
    col, row = (int(x) for x in project.target.split(","))
    if any((s.col, s.row) == (col, row) for s in state.settlements.values()):
        return "Others had already made camp there."
    source = max(state.settlements.values(), key=lambda s: s.population / capacity(state, s))
    moving = source.population * 0.3
    source.population -= moving
    camp = Settlement(
        state.new_id(),
        place_name(state, state.nation.culture, ctx.rng),
        col,
        row,
        moving,
        kind="village" if discoveries.fx(state, "settled") else "camp",
        cohesion=source.cohesion,
        plenty=source.plenty,
    )
    state.settlements[str(camp.id)] = camp
    return f"Families from {source.name} made a new camp: {camp.name}."


def _explore_finish(ctx, project):
    state = ctx.state
    m = game_map(state)
    ours = {tuple(t) for t in state.nation.territory}
    theirs = {tuple(t) for n in state.neighbours.values() for t in n.territory}
    frontier = {
        n
        for c in ours
        for n in neighbors(*c)
        if n not in ours and n not in theirs and 0 <= n[0] < len(m) and 0 <= n[1] < len(m[0])
    }
    best = sorted(frontier, key=lambda c: -forage_value(m[c[0]][c[1]]))[:EXPLORE_TILES]
    for c in best:
        state.nation.territory.append(list(c))
    met = []
    for n in state.neighbours.values():
        if not n.met and any(distance(c, tuple(t)) <= 3 for c in best for t in n.territory):
            n.met = True
            met.append(n.name)
    line = f"The people now range over {len(best)} more stretches of land." if best else ""
    if not best:
        line = "There was no unclaimed land within reach."
    if met:
        line += f" Out there, they met the {', '.join(met)}."
    return line


def _missing_work(work):
    def targets(state, char):
        return [
            (str(s.id), s.name)
            for s in state.settlements.values()
            if s.works.get(work, 0) < WORK_CAPS[work]
        ]

    return targets


def _build(work, line):
    def finish(ctx, project):
        camp = _camp(ctx.state, project)
        camp.works[work] = min(WORK_CAPS[work], camp.works.get(work, 0) + 1)
        return line.format(camp=camp.name)

    return finish


def _own_camp_missing(work):
    def targets(state, char):
        camp = state.settlement(char.settlement_id)
        if camp is None or camp.works.get(work, 0) >= WORK_CAPS[work]:
            return []
        return [(str(camp.id), camp.name)]

    return targets


def _paths_finish(ctx, project):
    seat = ctx.state.seat
    seat.works["paths"] = 1
    return "Paths now run between all the camps."


def _no_paths(state, char):
    return len(state.settlements) > 1 and not state.seat.works.get("paths")


def _respected_or_leader(state, char):
    return char.station == "leader" or char.means.get("regard") >= 30


def _teach_young_work(ctx, project):
    advance(ctx.nation, "lore", 1.5)


def _teach_young_finish(ctx, project):
    advance(ctx.nation, "lore", 4)
    ctx.char.means.add({"regard": 3})
    return "A new generation knows the songs by heart."


# --- other peoples -----------------------------------------------------------


def _met_targets(state, char):
    return [(str(n.id), f"the {n.name}") for n in state.neighbours.values() if n.met]


def _friendship_work(ctx, project):
    n = _neighbour(ctx.state, project)
    if n:
        n.relations = min(1.0, n.relations + 0.07)


def _friendship_finish(ctx, project):
    n = _neighbour(ctx.state, project)
    if not n:
        return "There was no one left to befriend."
    n.relations = min(1.0, n.relations + 0.15)
    theirs = [d for d in discoveries.available(ctx.state) if d.id in n.known]
    if theirs:
        d = ctx.rng.choice(theirs)
        discoveries.add_insight(ctx.state, d.id, d.cost * 0.3)
    return f"The {n.name} now speak of our people as friends."


def _trade_journey_finish(ctx, project):
    n = _neighbour(ctx.state, project)
    ctx.char.means.add({"food": 20})
    for category in ("tokens", "wares"):
        if category in ctx.nation.names:
            ctx.char.means.add({category: 6})
    if n:
        n.relations = min(1.0, n.relations + 0.1)
        theirs = [d for d in discoveries.available(ctx.state) if d.id in n.known]
        if theirs and ctx.rng.random() < 0.5:
            d = ctx.rng.choice(theirs)
            discoveries.add_insight(ctx.state, d.id, d.cost * 0.25)
        return f"You came back from the {n.name} laden, with stories to tell."
    return "You came back laden."


# --- family and following ------------------------------------------------------


def _young_child_targets(state, char):
    return [
        (str(c.id), c.name)
        for cid in char.children
        if (c := state.character(cid)) and c.alive and c.age(state.year) < ADULT_AGE - 2
    ]


def _raise_work(ctx, project):
    child = ctx.state.character(project.target)
    if child and child.alive:
        tendencies.pull_toward(child.tendencies, ctx.char.tendencies, 0.08)
        child.adjust_affinity(ctx.char.id, 0.06)
        ctx.char.adjust_affinity(child.id, 0.04)


def _raise_finish(ctx, project):
    child = ctx.state.character(project.target)
    if not child or not child.alive:
        return "The child you raised is gone."
    return f"{child.name} has grown up at your side, and is much like you."


def _apprentice_targets(state, char):
    return [
        (str(c.id), c.name)
        for c in state.living()
        if c.settlement_id == char.settlement_id
        and not c.is_player
        and c.id != char.id
        and ADULT_AGE <= c.age(state.year) < char.age(state.year)
    ][:4]


def _apprentice_work(ctx, project):
    who = ctx.state.character(project.target)
    if who and who.alive:
        tendencies.pull_toward(who.tendencies, ctx.char.tendencies, 0.06)
        who.adjust_affinity(ctx.char.id, 0.05)


def _apprentice_finish(ctx, project):
    ctx.char.means.add({"regard": 4})
    who = ctx.state.character(project.target)
    return f"{who.name} learned all you could teach." if who else "Your apprentice is gone."


def _following_work(ctx, project):
    ctx.char.means.add({"regard": 3})


def _following_finish(ctx, project):
    ctx.char.means.add({"regard": 8})
    return "A good many people now look to you first."


def _hoard_work(ctx, project):
    ctx.char.means.add({"food": 6})


def _shelter_finish(ctx, project):
    heal(ctx.char, 10)
    for cid in (ctx.char.spouse_id, *ctx.char.children):
        c = ctx.state.character(cid)
        if c and c.alive:
            heal(c, 8)
    return "Your family has a shelter that will stand for years."


def _not_leader(state, char):
    return char.station != "leader"


def _knows(did):
    return lambda state, char: did in state.nation.known


PROJECT_LIST = [
    ProjectDef(
        "pursue",
        "Work out {target}",
        "Spend your attention on an idea until it is understood.",
        (),
        ("studious",),
        0.01,
        0,
        {"hands": 2},
        work=_pursue_work,
        targets=_pursue_targets,
    ),
    ProjectDef(
        "explore",
        "Range beyond our lands",
        "Search out good land past the edge of the people's range.",
        ("leader", "hunter", "herder", "trader"),
        ("ambitious", "diligent"),
        0.0,
        3,
        {"hands": 4},
        finish=_explore_finish,
        scope="people",
    ),
    ProjectDef(
        "new_camp",
        "Lead families to a new camp ({target})",
        "Some families will make a new camp where the land is less crowded.",
        (),
        ("ambitious", "caring"),
        0.01,
        3,
        {"hands": 6, "food": 6},
        finish=_new_camp_finish,
        targets=_new_camp_sites,
        requires=_respected_or_leader,
        scope="people",
    ),
    ProjectDef(
        "gathering",
        "Make a gathering place at {target}",
        "A cleared ground with a great hearth, where all the camps can meet.",
        (),
        ("caring",),
        0.02,
        4,
        {"hands": 6},
        finish=_build("gathering", "{camp} has a gathering place."),
        targets=_missing_work("gathering"),
        scope="people",
    ),
    ProjectDef(
        "pits",
        "Dig store pits at {target}",
        "Lined pits that keep food through a lean year.",
        (),
        ("diligent",),
        0.01,
        3,
        {"hands": 5},
        finish=_build("pits", "New store pits were dug at {camp}."),
        targets=_missing_work("pits"),
        requires=_knows("food_keeping"),
        scope="people",
    ),
    ProjectDef(
        "teach_young",
        "Teach the young the old songs",
        "Years of evenings, until the young know everything you do.",
        ("keeper", "leader"),
        ("caring", "studious"),
        0.03,
        5,
        {"hands": 2},
        work=_teach_young_work,
        finish=_teach_young_finish,
    ),
    ProjectDef(
        "sacred",
        "Raise a sacred place at {target}",
        "Stones raised and a ground set apart for the unseen.",
        ("keeper", "leader"),
        ("contemplative",),
        0.02,
        6,
        {"hands": 4},
        finish=_build("sacred", "A sacred place stands at {camp}."),
        targets=_missing_work("sacred"),
        requires=_knows("shrine"),
        scope="people",
    ),
    ProjectDef(
        "fields",
        "Clear new fields at {target}",
        "Burn, clear and dig new ground for planting.",
        ("planter", "gatherer", "leader"),
        ("diligent",),
        0.01,
        4,
        {"hands": 4},
        finish=_build("fields", "New fields were opened at {camp}."),
        targets=_missing_work("fields"),
        requires=_knows("cultivation"),
        scope="people",
    ),
    ProjectDef(
        "herd",
        "Build up the herd at {target}",
        "Breed and guard the beasts until the herd is large.",
        ("herder",),
        ("diligent",),
        0.01,
        4,
        {"hands": 3},
        finish=_build("herd", "The herds around {camp} have grown."),
        targets=_own_camp_missing("herd"),
    ),
    ProjectDef(
        "weir",
        "Build a fish weir at {target}",
        "Stakes and woven fences to trap fish in the shallows.",
        ("fisher",),
        ("diligent",),
        0.01,
        3,
        {"hands": 3},
        finish=_build("weir", "A new weir catches fish near {camp}."),
        targets=_own_camp_missing("weir"),
    ),
    ProjectDef(
        "friendship",
        "Seek friendship with {target}",
        "Visits, gifts and shared meals, year after year.",
        ("leader", "trader"),
        ("generous",),
        0.03,
        3,
        {"food": 5},
        work=_friendship_work,
        finish=_friendship_finish,
        targets=_met_targets,
        scope="people",
    ),
    ProjectDef(
        "trade_journey",
        "Journey to {target} to trade",
        "Carry what our people make to another people, and bring back what they have.",
        ("trader",),
        ("diligent", "acquisitive"),
        0.0,
        2,
        {"food": 4},
        finish=_trade_journey_finish,
        targets=_met_targets,
        common=False,
    ),
    ProjectDef(
        "raise_child",
        "Raise {target} by your side",
        "Keep the child close and shape who they become.",
        (),
        ("caring",),
        0.03,
        6,
        {"hands": 1},
        work=_raise_work,
        finish=_raise_finish,
        targets=_young_child_targets,
        common=False,
    ),
    ProjectDef(
        "apprentice",
        "Take {target} as your apprentice",
        "Teach someone younger everything you know.",
        ("keeper", "maker", "hunter", "gatherer", "planter", "herder", "fisher", "trader"),
        ("generous", "studious"),
        0.02,
        4,
        {"hands": 1},
        work=_apprentice_work,
        finish=_apprentice_finish,
        targets=_apprentice_targets,
        common=False,
    ),
    ProjectDef(
        "following",
        "Gather a following",
        "Win people over, one favour and one story at a time.",
        (),
        ("ambitious",),
        -0.01,
        4,
        {"food": 3},
        work=_following_work,
        finish=_following_finish,
        requires=_not_leader,
        common=False,
    ),
    ProjectDef(
        "hoard",
        "Put food by for your own",
        "Quietly build up your family's stores against hard years.",
        (),
        ("acquisitive",),
        -0.02,
        3,
        {"hands": 2},
        work=_hoard_work,
        finish=lambda ctx, p: "Your family has food put by that no one else knows about.",
        common=False,
    ),
    ProjectDef(
        "shelter",
        "Build your family a lasting shelter",
        "Timber, earth and hide, built to stand for years.",
        (),
        ("caring", "diligent"),
        0.01,
        2,
        {"hands": 3},
        finish=_shelter_finish,
        requires=_knows("dwellings"),
        common=False,
    ),
    ProjectDef(
        "paths",
        "Clear paths between the camps",
        "Trodden, marked ways, so the camps can reach one another in any season.",
        (),
        ("caring", "diligent"),
        0.02,
        4,
        {"hands": 4},
        finish=_paths_finish,
        requires=_no_paths,
        scope="people",
    ),
]

PROJECTS = {p.id: p for p in PROJECT_LIST}


@dataclass
class ProjectOption:
    definition: ProjectDef
    target: str | None
    name: str
    years: int
    cost: dict


@dataclass(frozen=True)
class _Help:
    """What helping with a project costs, priced like an action."""

    cost: dict
    tags: tuple
    scope: str = "own"


def _working_at(state, char, kind, target):
    return any(
        p.kind == kind and p.target == target and char.id in (p.leader_id, *p.helpers)
        for p in state.projects.values()
    )


def options_for(state, char):
    """Projects this character could start now."""
    leading_idea = any(
        p.kind == "pursue" for p in state.projects.values() if char.id in (p.leader_id, *p.helpers)
    )
    under_way = {(p.kind, p.target) for p in state.projects.values() if p.common}
    out = []
    for d in PROJECT_LIST:
        if d.stations and char.station not in d.stations:
            continue
        if d.id == "pursue" and leading_idea:
            continue  # one idea at a time
        if d.requires and not d.requires(state, char):
            continue
        targets = d.targets(state, char) if d.targets else [(None, "")]
        for target, label in targets:
            if (d.id, target) in under_way or _working_at(state, char, d.id, target):
                continue  # already being worked: join it instead
            years = _pursue_years(state, char, target) if d.id == "pursue" else d.years
            cost = effective_cost(state, char, d)
            out.append(ProjectOption(d, target, d.name.format(target=label), years, cost))
    return out


def display_name(state, project):
    d = PROJECTS[project.kind]
    label = ""
    if project.target is not None:
        if project.kind == "pursue":
            label = discoveries.QUESTIONS.get(project.target, project.target)
        elif project.kind == "new_camp":
            col, row = (int(x) for x in project.target.split(","))
            t = tile(state, col, row)
            seat = (state.seat.col, state.seat.row)
            label = f"{t['biome'].lower()} to the {direction(seat, (col, row))}"
        else:
            label = _fallback_label(state, project)
    return d.name.format(target=label)


def _fallback_label(state, project):
    for lookup in (state.settlement, state.neighbour, state.character):
        found = lookup(project.target)
        if found is not None:
            name = getattr(found, "name", "")
            return f"the {name}" if lookup == state.neighbour else name
    return "it"


def start(state, char, option):
    d = option.definition
    project = Project(
        id=state.new_id(),
        kind=d.id,
        leader_id=char.id,
        needed=float(option.years),
        target=option.target,
        common=d.common,
        started=state.year,
        started_by=char.full_name,
    )
    state.projects[str(project.id)] = project
    return project


def yearly_cost(state, project):
    d = PROJECTS[project.kind]
    char = state.character(project.leader_id)
    return effective_cost(state, char, d)


def help_cost(state, char, project):
    return effective_cost(state, char, _Help(HELP_COST, PROJECTS[project.kind].tags))


def rally_cost(state, char):
    return effective_cost(state, char, _Help(RALLY_COST, RALLY_TAGS))


def payer(state, project):
    d = PROJECTS[project.kind]
    char = state.character(project.leader_id)
    return budget_for(state, char, d)


def is_finished(state, project):
    if project.kind == "pursue":
        return project.target in state.nation.known
    return project.done >= project.needed - 1e-9


def progress(state, project):
    """How far along it is, 0..1."""
    if project.kind == "pursue":
        return discoveries.progress(state, discoveries.DISCOVERIES[project.target])
    return min(1.0, project.done / project.needed) if project.needed else 1.0


def years_left(state, project):
    if project.kind == "pursue":
        d = discoveries.DISCOVERIES[project.target]
        left = max(0.0, d.cost - state.nation.insight.get(d.id, 0))
        per_year = max(1.0, project.rate * PURSUE_RATE)
        return max(1, math.ceil(left / per_year))
    return max(1, math.ceil((project.needed - project.done) / max(0.5, project.rate)))


def progress_word(fraction):
    if fraction >= 0.75:
        return "nearly done"
    if fraction >= 0.45:
        return "half done"
    if fraction >= 0.15:
        return "under way"
    return "just begun"


# --- who works on what --------------------------------------------------------


def fits(char, d):
    """Whether this is the character's kind of work."""
    return not d.stations or char.station in d.stations


def can_help(state, char, project):
    if not project.common or char.id == project.leader_id or char.id in project.helpers:
        return False
    if project.kind == "pursue":
        domain = discoveries.DISCOVERIES[project.target].domain
        return domain in STATIONS[char.station].domains
    return True


def joinable(state, char):
    """The people's works this character could help with, or take up."""
    return [p for p in state.projects.values() if can_help(state, char, p)]


def join(state, char, project):
    """Help with a project, or take it up if no one leads it. Returns a chronicle line."""
    name = _lower_first(display_name(state, project))
    if project.leader_id is None:
        project.leader_id = char.id
        return f"You took up {name}, begun by {project.started_by}."
    project.helpers.append(char.id)
    leader = state.character(project.leader_id)
    return f"You joined {leader.full_name} in {name}."


def leave(state, char, project):
    """Stop working on a project. The people's works pass on; personal ones end."""
    if char.id in project.helpers:
        project.helpers.remove(char.id)
        return None
    if project.leader_id == char.id:
        return pass_on(state, project, exclude=(char.id,))
    return None


def pass_on(state, project, exclude=()):
    """Find someone to carry on a project whose leader is gone. Returns a line or None."""
    if not project.common:
        state.projects.pop(str(project.id), None)
        return None
    name = _lower_first(display_name(state, project))

    def free(c):
        return c and c.alive and not c.is_player and c.id not in exclude

    helpers = [c for c in map(state.character, project.helpers) if free(c)]
    leader = state.leader
    if helpers:
        new = helpers[0]
        project.helpers.remove(new.id)
    elif free(leader) and len(state.projects_of(leader.id)) < 2:
        new = leader
    else:
        elders = [c for c in state.living() if c.is_elder and free(c)]
        elders = [c for c in elders if not state.projects_of(c.id)]
        new = elders[0] if elders else None
    project.helpers = [h for h in project.helpers if h not in exclude]
    if new is None:
        project.leader_id = None
        return f"No one took up {name}; it lies unfinished."
    project.leader_id = new.id
    return f"{new.full_name} took up {name}."


def rally(state, char, project):
    """Call people at large to help. Returns a chronicle line."""
    added = 1 + char.means.get("regard") / 30
    project.support += added
    families = max(2, round(added * 4))
    name = _lower_first(display_name(state, project))
    return f"You called on others to help with {name}; some {families} families came."


def _drop_absent_helpers(state, project):
    project.helpers = [
        h
        for h in project.helpers
        if (c := state.character(h)) and c.alive and h != project.leader_id
    ]


def _note_for_player(state, text):
    """Something the player should be stopped for, from work done outside their own turn."""
    state.__dict__.setdefault("_player_notes", []).append(text)


def player_notes(state):
    return state.__dict__.pop("_player_notes", [])


def work_year(state, project, rng):
    """One year of work. Returns (line or None, outcome): outcome is "", "stalled" or "done"."""
    d = PROJECTS[project.kind]
    _drop_absent_helpers(state, project)
    char = state.character(project.leader_id)
    if char is None or not char.alive:
        line = pass_on(state, project)
        char = state.character(project.leader_id)
        if char is None:
            return line, ""
    if is_finished(state, project):
        return _finish(state, project, char, rng), "done"
    cost = yearly_cost(state, project)
    budget = payer(state, project)
    if not budget.can_afford(cost):
        project.stalled = True
        return f"{display_name(state, project)} made no progress for want of means.", "stalled"
    project.stalled = False
    budget.spend(cost)

    workers = [(char, 1.0)]
    for helper in map(state.character, list(project.helpers)):
        price = help_cost(state, helper, project)
        if helper.means.can_afford(price):
            helper.means.spend(price)
            workers.append((helper, FIT_EFFORT if fits(helper, d) else HELPER_EFFORT))
    rate = sum(e for _, e in workers) + SUPPORT_EFFORT * project.support
    project.rate = rate
    project.support *= SUPPORT_FADE
    for worker, _ in workers:
        if worker.is_player and worker.full_name not in project.worked_by:
            project.worked_by.append(worker.full_name)

    ctx = Ctx(state, char, rng)
    if project.kind == "pursue":
        insight = sum(pursue_rate(state, w) * e for w, e in workers)
        insight += SUPPORT_EFFORT * project.support * NPC_PURSUE_RATE
        discoveries.add_insight(state, project.target, insight)
        project.done += rate
        return None, ""  # understood when the people settle what they know
    project.done += rate
    line = d.work(ctx, project) if d.work else None
    if is_finished(state, project):
        return _finish(state, project, char, rng), "done"
    return line, ""


def _finish(state, project, char, rng):
    d = PROJECTS[project.kind]
    name = display_name(state, project)
    del state.projects[str(project.id)]
    line = d.finish(Ctx(state, char, rng), project) if d.finish else f"{name}: done."
    if project.worked_by and project.common:
        record(state, f"{line} (Begun by {project.started_by}.)", project.worked_by)
    if state.player_id in (project.leader_id, *project.helpers):
        _note_for_player(state, f"Finished: {name}.")
    return line


def record(state, text, names):
    """Remember something the player's lives had a hand in."""
    state.legacy.append({"year": state.year, "text": text, "names": list(names)})
    del state.legacy[:-LEGACY_LIMIT]


def abandon(state, project):
    state.projects.pop(str(project.id), None)


def _lower_first(text):
    return text[:1].lower() + text[1:]
