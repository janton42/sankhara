"""Turn simulation numbers into the words the player sees.

Some values are shown only as words, so the player gets a feel for them
rather than a number to optimise.
"""


def _band(value, bands):
    for threshold, word in bands:
        if value >= threshold:
            return word
    return bands[-1][1]


def health_word(health):
    return _band(
        health, [(80, "hale"), (60, "well"), (40, "weary"), (20, "ailing"), (0, "failing")]
    )


def stability_word(stability):
    return _band(
        stability,
        [(75, "calm"), (55, "settled"), (40, "restless"), (25, "unruly"), (0, "in turmoil")],
    )


def prosperity_word(prosperity):
    return _band(
        prosperity,
        [(75, "thriving"), (55, "comfortable"), (40, "getting by"), (25, "poor"), (0, "destitute")],
    )


def level_word(value):
    """For learning and the arts."""
    return _band(
        value,
        [(70, "renowned"), (50, "flourishing"), (30, "growing"), (15, "modest"), (0, "scant")],
    )


def harvest_word(food_balance, population):
    ratio = food_balance / max(1.0, population * 0.1)
    return _band(
        ratio,
        [(0.2, "plenty"), (0.05, "enough"), (0.0, "just enough"), (-0.15, "short"), (-9, "hunger")],
    )


def budget_text(budget):
    return f"{budget.food:.0f} food  ·  {budget.goods:.0f} goods  ·  {budget.coin:.0f} coin"


def cost_text(cost):
    if not cost:
        return "no cost"
    return ", ".join(f"{amount:g} {category}" for category, amount in cost.items())


def population_text(population):
    if population >= 1000:
        return f"{population / 1000:.1f}k"
    return f"{population:.0f}"
