"""Simplified choices for tracked NPCs: the same tendency model as the player, decided
coarsely. Rulers and nobles' choices act on the world; everyone else's only shape
who they are becoming."""

import math

from sankhara.sim import tendencies
from sankhara.sim.actions import Ctx, actions_for, budget_for, effective_cost
from sankhara.sim.stations import ADULT_AGE

NPC_KARMA_RATE = 0.05
WORLD_ACTING = ("ruler", "noble")


def situational(state, char, action):
    """NPC rulers respond to the realm's state, whatever their inclinations."""
    if char.station != "ruler":
        return 1.0
    nation = state.nation
    hungry = any(s.food_balance < 0 for s in state.settlements.values())
    if action.id == "relieve":
        return 6.0 if hungry else 0.2
    poor = nation.treasury.coin < 120
    if action.id == "raise_taxes":
        if nation.tax_rate >= 0.3 or nation.treasury.coin > 400:
            return 0.0
        return 4.0 if poor and nation.stability > 40 else 0.5
    if action.id == "lower_taxes":
        if nation.tax_rate <= 0.08 or (poor and nation.stability > 40):
            return 0.1
        return 3.0 if nation.stability < 40 or nation.tax_rate > 0.25 else 1.0
    if action.id in ("hold_court", "grievances"):
        return 3.0 if nation.stability < 40 else 1.0
    if action.id in ("irrigation", "granary"):
        return 3.0 if hungry else 1.0
    return 1.0


def choose(state, char, count, rng):
    """Pick `count` affordable station actions, favouring what they're inclined to."""
    options = [a for a in actions_for(state, char) if a.stations]
    picked = []
    for _ in range(count):
        weights = []
        for a in options:
            if a in picked:
                weights.append(0.0)
                continue
            budget = budget_for(state, char, a)
            if not budget.can_afford(effective_cost(char, a)):
                weights.append(0.0)
                continue
            pull = math.exp(3 * tendencies.affinity(char.tendencies, a.tags))
            weights.append(pull * situational(state, char, a))
        if not any(weights):
            break
        picked.append(rng.choices(options, weights)[0])
    return picked


def npc_year(state, protect=()):
    """Every tracked adult NPC makes their choices for the year. Returns notable log lines."""
    rng = state.rng()
    notes = []
    for char in list(state.living()):
        if char.is_player or char.id in protect or char.age(state.year) < ADULT_AGE:
            continue
        count = 2 if char.station == "ruler" else 1
        for action in choose(state, char, count, rng):
            tendencies.strengthen(char.tendencies, action.tags)
            char.karma = tendencies.clamp(
                char.karma + NPC_KARMA_RATE * tendencies.tag_karma(action.tags)
            )
            if char.station in WORLD_ACTING:
                budget_for(state, char, action).spend(effective_cost(char, action))
                result = action.effect(Ctx(state, char, rng))
                if char.station == "ruler":
                    notes.append(f"{char.full_name}: {action.name.lower()}. {result}")
    return notes
