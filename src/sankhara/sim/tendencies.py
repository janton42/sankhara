"""Habitual tendencies: the inclinations a character's choices build up.

They are never shown. The player only feels them: actions they lean toward cost
less and are offered first, and actions against the grain cost more. Choosing an
action strengthens its tags, and setting aside a project weakens them, both at a
fixed rate.
"""

TAGS = (
    "generous",
    "caring",
    "contemplative",
    "studious",
    "diligent",
    "ambitious",
    "acquisitive",
    "indulgent",
    "harsh",
)

# How wholesome each inclination is. Used only when karma shapes the next life's
# inclinations, and for NPCs' simplified karma.
VALENCE = {
    "generous": 1.0,
    "caring": 1.0,
    "contemplative": 0.5,
    "studious": 0.3,
    "diligent": 0.3,
    "ambitious": -0.2,
    "acquisitive": -0.6,
    "indulgent": -0.6,
    "harsh": -1.0,
}

SHIFT_STEP = 0.05  # strengthening from choosing an action
DECLINE_STEP = 0.04  # weakening from setting something aside
COST_SWING = 0.3  # costs range from 70% (strong pull) to 130% (strong friction)
CARRY = 0.8  # how much of a life's pattern carries into the next
KARMA_SHAPING = 0.25  # how strongly karma tilts the next life's inclinations


def clamp(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, x))


def affinity(tendencies, tags):
    """How strongly a character leans toward an action with these tags (-1..1)."""
    if not tags:
        return 0.0
    return sum(tendencies.get(t, 0.0) for t in tags) / len(tags)


def cost_multiplier(tendencies, tags):
    return 1.0 - COST_SWING * affinity(tendencies, tags)


def strengthen(tendencies, tags, step=SHIFT_STEP):
    for t in tags:
        tendencies[t] = clamp(tendencies.get(t, 0.0) + step)


def weaken(tendencies, tags, step=DECLINE_STEP):
    for t in tags:
        tendencies[t] = clamp(tendencies.get(t, 0.0) - step)


def pull_toward(tendencies, model, rate):
    """Shift one character's inclinations part of the way toward another's (upbringing, counsel)."""
    for t in TAGS:
        current = tendencies.get(t, 0.0)
        tendencies[t] = clamp(current + rate * (model.get(t, 0.0) - current))


def carry_into_next_life(tendencies, karma):
    """The pattern at death, faded a little and tilted by karma, becomes the new default."""
    return {
        t: clamp(CARRY * tendencies.get(t, 0.0) + KARMA_SHAPING * karma * VALENCE[t]) for t in TAGS
    }


def random_tendencies(rng, spread=0.2):
    return {t: rng.uniform(-spread, spread) for t in TAGS}


def tag_karma(tags):
    """Simplified karma for NPC choices: the average wholesomeness of what they chose."""
    if not tags:
        return 0.0
    return sum(VALENCE[t] for t in tags) / len(tags)
