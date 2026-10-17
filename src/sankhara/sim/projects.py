"""Undertakings that take several years of someone's attention.

A project holds one attention slot year after year until it is finished,
abandoned or stalls for want of means. It is paid for every year it is worked,
and its inclination tags and karma count each year too: carrying something on
is a choice made again every year.
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
    def requires(state, char):
        camp = state.settlement(char.settlement_id)
        return camp is not None and camp.works.get(work, 0) < WORK_CAPS[work]

    return requires


def _build_own(work, line):
    def finish(ctx, project):
        camp = ctx.settlement
        camp.works[work] = min(WORK_CAPS[work], camp.works.get(work, 0) + 1)
        return line.format(camp=camp.name)

    return finish


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
        ("leader", "hunter"),
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
        ("leader",),
        ("ambitious", "caring"),
        0.01,
        3,
        {"hands": 6, "food": 6},
        finish=_new_camp_finish,
        targets=_new_camp_sites,
        scope="people",
    ),
    ProjectDef(
        "gathering",
        "Make a gathering place at {target}",
        "A cleared ground with a great hearth, where all the camps can meet.",
        ("leader",),
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
        ("leader", "gatherer"),
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
        ("planter", "leader"),
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
        "Build up the herd",
        "Breed and guard the beasts until the herd is large.",
        ("herder",),
        ("diligent",),
        0.01,
        4,
        {"hands": 3},
        finish=_build_own("herd", "The herds around {camp} have grown."),
        requires=_own_camp_missing("herd"),
    ),
    ProjectDef(
        "weir",
        "Build a fish weir",
        "Stakes and woven fences to trap fish in the shallows.",
        ("fisher",),
        ("diligent",),
        0.01,
        3,
        {"hands": 3},
        finish=_build_own("weir", "A new weir catches fish near {camp}."),
        requires=_own_camp_missing("weir"),
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


def options_for(state, char):
    """Projects this character could start now."""
    mine = state.projects_of(char.id)
    busy = {(p.kind, p.target) for p in mine}
    out = []
    for d in PROJECT_LIST:
        if d.stations and char.station not in d.stations:
            continue
        if d.id == "pursue" and any(p.kind == "pursue" for p in mine):
            continue  # one idea at a time
        if d.requires and not d.requires(state, char):
            continue
        targets = d.targets(state, char) if d.targets else [(None, "")]
        for target, label in targets:
            if (d.id, target) in busy:
                continue
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
        elif d.targets is not None:
            char = state.character(project.leader_id)
            label = next(
                (lbl for tid, lbl in d.targets(state, char) if tid == project.target), ""
            ) or _fallback_label(state, project)
    return d.name.format(target=label)


def _fallback_label(state, project):
    for lookup in (state.settlement, state.neighbour, state.character):
        found = lookup(project.target)
        if found is not None:
            name = getattr(found, "name", "")
            return f"the {name}" if lookup == state.neighbour else name
    return "it"


def start(state, char, option, slot=0):
    project = Project(
        id=state.new_id(),
        kind=option.definition.id,
        leader_id=char.id,
        years_needed=option.years,
        target=option.target,
        slot=slot,
        started=state.year,
    )
    state.projects[str(project.id)] = project
    return project


def yearly_cost(state, project):
    d = PROJECTS[project.kind]
    char = state.character(project.leader_id)
    return effective_cost(state, char, d)


def payer(state, project):
    d = PROJECTS[project.kind]
    char = state.character(project.leader_id)
    return budget_for(state, char, d)


def is_finished(state, project):
    if project.kind == "pursue":
        return project.target in state.nation.known
    return project.years_done >= project.years_needed


def work_year(state, project, rng):
    """One year of work. Returns (line or None, outcome): outcome is "", "stalled" or "done"."""
    d = PROJECTS[project.kind]
    char = state.character(project.leader_id)
    if char is None or not char.alive:
        del state.projects[str(project.id)]
        return None, ""
    if is_finished(state, project):
        return _finish(state, project, char, rng), "done"
    cost = yearly_cost(state, project)
    budget = payer(state, project)
    if not budget.can_afford(cost):
        project.stalled = True
        return f"{display_name(state, project)} made no progress for want of means.", "stalled"
    project.stalled = False
    budget.spend(cost)
    project.years_done += 1
    ctx = Ctx(state, char, rng)
    line = d.work(ctx, project) if d.work else None
    if project.kind == "pursue":
        # an idea is understood when the people settle what they know (see game.end_year)
        project.years_needed = max(project.years_done + 1, project.years_needed)
        return line, ""
    if is_finished(state, project):
        return _finish(state, project, char, rng), "done"
    return line, ""


def _finish(state, project, char, rng):
    d = PROJECTS[project.kind]
    name = display_name(state, project)
    del state.projects[str(project.id)]
    if d.finish:
        return d.finish(Ctx(state, char, rng), project)
    return f"{name}: done."


def abandon(state, project):
    state.projects.pop(str(project.id), None)
