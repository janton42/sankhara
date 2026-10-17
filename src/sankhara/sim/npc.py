"""Simplified choices for tracked NPCs: the same tendency model as the player, decided
coarsely. The leader's deeds act on the people; everyone's projects run (working at
ideas, raising children, building), and they join the people's works others have
begun, more readily when the one leading is respected or liked, or has called on
people to help. Every choice shapes who they are becoming."""

import math

from sankhara.sim import projects, tendencies
from sankhara.sim.actions import Ctx, actions_for, budget_for, effective_cost
from sankhara.sim.nation import capacity
from sankhara.sim.stations import ADULT_AGE

NPC_KARMA_RATE = 0.05
START_CHANCE = 0.35  # an idle ordinary NPC taking something on, per year
DEED_REGARD = 1.0
JOIN_WEIGHT = 1.5  # helping with what is under way comes more naturally than beginning anew
LEAVE_CHANCE = 0.12
ELDER_REGARD = 4.0


def _crowded(state):
    return any(s.population > 0.8 * capacity(state, s) for s in state.settlements.values())


def situational(state, char, action_id):
    """The leader responds to the people's state, whatever their inclinations."""
    if char.station != "leader":
        # ordinary people rarely uproot families or set out for new land on their own
        return 0.2 if action_id in ("new_camp", "explore") else 1.0
    nation = state.nation
    hungry = any(s.food_balance < 0 for s in state.settlements.values())
    if action_id == "open_stores":
        return 6.0 if hungry else 0.2
    if action_id in ("call_together", "settle_quarrels"):
        return 3.0 if nation.cohesion < 40 else 0.7
    if action_id == "great_hunt":
        return 2.0 if nation.stores.get("food") < 30 else 0.7
    if action_id == "new_camp":
        return 5.0 if _crowded(state) else 0.3
    if action_id == "explore":
        return 3.0 if _crowded(state) else 0.4
    if action_id == "friendship":
        return 3.0 if any(n.met and n.relations < 0 for n in state.neighbours.values()) else 0.6
    if action_id == "pursue":
        return 2.0
    return 1.0


def _pick(options, weights, rng):
    if not any(weights):
        return None
    return rng.choices(options, weights)[0]


def choose_deed(state, char, rng):
    options = actions_for(state, char)
    weights = []
    for a in options:
        if not budget_for(state, char, a).can_afford(effective_cost(state, char, a)):
            weights.append(0.0)
            continue
        pull = math.exp(3 * tendencies.affinity(char.tendencies, a.tags))
        weights.append(pull * situational(state, char, a.id))
    return _pick(options, weights, rng)


def _draw(state, project):
    """How strongly a work draws others in: people called to it, and who leads it."""
    leader = state.character(project.leader_id)
    pull = 1 + project.support / 2
    if leader is not None:
        pull *= 1 + leader.means.get("regard") / 40
    return pull


def choose_work(state, char, rng):
    """Something to take on: begin a work, help with one, or take up an unfinished one.

    Returns ("start", ProjectOption), ("join", Project) or None.
    """
    choices, weights = [], []
    for o in projects.options_for(state, char):
        d = o.definition
        if not budget_for(state, char, d).can_afford(o.cost):
            continue
        choices.append(("start", o))
        pull = math.exp(3 * tendencies.affinity(char.tendencies, d.tags))
        weights.append(pull * situational(state, char, d.id))
    for p in projects.joinable(state, char):
        d = projects.PROJECTS[p.kind]
        if p.leader_id is None:
            price = budget_for(state, char, d).can_afford(effective_cost(state, char, d))
        else:
            price = char.means.can_afford(projects.help_cost(state, char, p))
        if not price:
            continue
        choices.append(("join", p))
        pull = math.exp(3 * tendencies.affinity(char.tendencies, d.tags))
        liking = 1 + max(0.0, char.feels(p.leader_id)) if p.leader_id else 1.5
        weights.append(
            JOIN_WEIGHT * pull * liking * _draw(state, p) * situational(state, char, d.id)
        )
    return _pick(choices, weights, rng)


def _act(state, char, tags, karma):
    tendencies.strengthen(char.tendencies, tags)
    intention = (karma * 10 + tendencies.tag_karma(tags)) / 2
    char.karma = tendencies.clamp(char.karma + NPC_KARMA_RATE * intention)


def npc_year(state, protect=()):
    """Every tracked adult NPC acts for the year. Returns notable log lines."""
    rng = state.rng()
    notes = []
    for char in list(state.living()):
        if char.is_player or char.id in protect or char.age(state.year) < ADULT_AGE:
            continue
        leading = char.station == "leader"

        # take something on, or drift away from what they were helping with
        for project in state.helping(char.id):
            if rng.random() < LEAVE_CHANCE:
                projects.leave(state, char, project)
        busy = len(state.projects_of(char.id)) + len(state.helping(char.id))
        limit = 2 if leading else 1
        if busy < limit and (leading or char.is_elder or rng.random() < START_CHANCE):
            choice = choose_work(state, char, rng)
            if choice and choice[0] == "start":
                projects.start(state, char, choice[1])
            elif choice:
                projects.join(state, char, choice[1])
        for project in state.helping(char.id):
            d = projects.PROJECTS[project.kind]
            _act(state, char, d.tags, d.karma)
        for project in state.projects_of(char.id):
            d = projects.PROJECTS[project.kind]
            line, outcome = projects.work_year(state, project, rng)
            if outcome == "stalled":
                if rng.random() < 0.3:
                    line = projects.leave(state, char, project)
                    if line and project.common:
                        notes.append(line)
                continue
            _act(state, char, d.tags, d.karma)
            if line and outcome == "done" and (leading or project.common):
                notes.append(f"{char.full_name}: {line}")

        # and a deed
        deed = choose_deed(state, char, rng)
        if deed is None:
            continue
        _act(state, char, deed.tags, deed.karma)
        # what they do earns them standing, as the player's deeds do
        char.means.add({"regard": ELDER_REGARD if char.is_elder else DEED_REGARD})
        if leading:
            cost = effective_cost(state, char, deed)
            budget_for(state, char, deed).spend(cost)
            result = deed.effect(Ctx(state, char, rng))
            if deed.id in ("open_stores", "drive_out", "larger_share", "call_together"):
                notes.append(f"{char.full_name}: {result}")
    return notes
