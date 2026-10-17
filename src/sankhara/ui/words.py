"""Turn simulation numbers into the words the player sees.

Some values are shown only as words, so the player gets a feel for them
rather than a number to optimise.
"""

from sankhara.sim.discoveries import categories, category_name


def _band(value, bands):
    for threshold, word in bands:
        if value >= threshold:
            return word
    return bands[-1][1]


def health_word(health):
    return _band(
        health, [(80, "hale"), (60, "well"), (40, "weary"), (20, "ailing"), (0, "failing")]
    )


def cohesion_word(cohesion):
    return _band(
        cohesion,
        [(75, "close-knit"), (55, "at ease"), (40, "restless"), (25, "quarrelsome"), (0, "torn")],
    )


def plenty_word(plenty):
    return _band(
        plenty,
        [(75, "well fed"), (55, "comfortable"), (40, "getting by"), (25, "lean"), (0, "starving")],
    )


def lore_word(value):
    return _band(
        value,
        [(70, "deep"), (50, "rich"), (30, "growing"), (15, "thin"), (0, "scant")],
    )


def food_word(food_balance, population):
    ratio = food_balance / max(1.0, population * 0.1)
    return _band(
        ratio,
        [
            (0.2, "plenty"),
            (0.05, "enough"),
            (-0.05, "just enough"),
            (-0.15, "short"),
            (-9, "hunger"),
        ],
    )


def regard_word(regard):
    return _band(
        regard,
        [(70, "much respected"), (40, "respected"), (15, "known"), (0, "little regarded")],
    )


def budget_text(budget, nation):
    parts = []
    for c in categories(nation):
        if c == "regard" and budget is nation.stores:
            continue
        parts.append(f"{budget.get(c):.0f} {category_name(nation, c)}")
    return "  ·  ".join(parts)


def cost_text(cost, nation):
    if not cost:
        return "no cost"
    return ", ".join(f"{amount:g} {category_name(nation, c)}" for c, amount in cost.items())


def years_text(years, about=False):
    word = "year" if years == 1 else "years"
    return f"{'about ' if about else ''}{years} {word}"


def population_text(population):
    if population >= 1000:
        return f"{population / 1000:.1f}k"
    return f"{population:.0f}"
