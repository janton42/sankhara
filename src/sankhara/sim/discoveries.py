"""The web of things a people can come to know.

Nothing here is a fixed tree to march through. A discovery becomes possible only
when its circumstances are met (the land, what the people already know, who they
have met), and it grows from three sources: the people's ordinary practice (a
little every year), someone setting out to work at it (a project), and chance
events. Many discoveries settle into one of several forms: how exchange works,
how leaders are chosen, how the fields are held. The form follows whoever worked
it out, or else the people's own inclinations, and it changes what follows.

Effects are combined across everything known:
- keys ending in `_mult` multiply (food_mult, capacity_mult, insight_mult,
  plague_mult, raid_mult, contact_mult)
- numbers add (spoilage, health, cohesion, plenty, lore, stores_share, leader_regard)
- `fishing` and `settled` are flags
- `succession`, `title:<role>` and `category:<id>` are applied once, when learned
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from sankhara.sim import tendencies
from sankhara.sim.stations import ADULT_AGE
from sankhara.sim.world import is_grassy, is_watery, range_has, resource

ONE_OFF_PREFIXES = ("succession", "title:", "category:")


@dataclass(frozen=True)
class Form:
    id: str
    name: str
    text: str
    tags: tuple
    effects: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Discovery:
    id: str
    name: str  # once known
    hint: str  # while it is only stirring
    text: str  # what it means for the people, once known
    cost: float  # insight needed
    domain: str  # land, craft, lore or kin: who can work at it
    requires: tuple = ()  # all of these
    requires_any: tuple = ()  # at least one of these
    condition: Callable | None = field(default=None, repr=False)
    effects: dict = field(default_factory=dict)
    forms: tuple = ()

    def form(self, form_id):
        return next((f for f in self.forms if f.id == form_id), None)


def _water(state):
    return range_has(state, is_watery)


def _grass(state):
    return range_has(state, is_grassy)


def _game(state):
    return range_has(state, lambda t: resource(t, "animal_food") >= 0.6)


def _met_anyone(state):
    return any(n.met for n in state.neighbours.values())


def _many(n):
    return lambda state: state.total_population() >= n


DISCOVERY_LIST = [
    # --- known from the start -------------------------------------------------
    Discovery(
        "fire",
        "Keeping fire",
        "",
        "Fire is carried from camp to camp and never allowed to die.",
        0,
        "craft",
    ),
    Discovery(
        "stone_tools",
        "Stone edges",
        "",
        "Flint and stone are knapped into blades and scrapers.",
        0,
        "craft",
    ),
    Discovery(
        "songs",
        "The old songs",
        "",
        "What the people know lives in songs and stories passed down by the old.",
        0,
        "lore",
    ),
    Discovery(
        "spirits",
        "The unseen",
        "",
        "The world is full of powers that must be heeded.",
        0,
        "lore",
        forms=(
            Form(
                "ancestors",
                "The ancestors watch",
                "The dead stay near and must be honoured.",
                ("caring",),
                {"cohesion": 2},
            ),
            Form(
                "beasts",
                "The spirits of beasts",
                "Every animal has a spirit that must be asked before a kill.",
                ("contemplative",),
                {"lore": 0.3},
            ),
            Form(
                "sky",
                "The powers of the sky",
                "Storm, sun and moon decide the people's fortunes.",
                ("ambitious",),
                {"leader_regard": 1},
            ),
        ),
    ),
    # --- the land -------------------------------------------------------------
    Discovery(
        "food_keeping",
        "Keeping food",
        "Some wonder whether meat and roots could be made to last through the lean months.",
        "Drying, smoking and covered pits keep food through the lean months.",
        65,
        "land",
        requires=("fire",),
        effects={"spoilage": -0.12},
    ),
    Discovery(
        "wild_grain",
        "Knowing the wild grasses",
        "The gatherers talk of grasses whose seeds can be eaten, if anyone could tell which.",
        "The people know which wild grasses give seed worth gathering and when.",
        80,
        "land",
        condition=_grass,
        effects={"food_mult": 1.08},
    ),
    Discovery(
        "fishing",
        "Taking fish",
        "Children watch the fish in the shallows and wonder how they might be caught.",
        "Lines, traps and nets bring fish from the water.",
        70,
        "land",
        requires=("cordage",),
        condition=_water,
        effects={"fishing": True},
    ),
    Discovery(
        "taming",
        "Taming beasts",
        "A hunter has been feeding an orphaned young beast. It follows him about.",
        "Some beasts can be kept, fed and made to stay near people.",
        90,
        "land",
        requires=("hides",),
        condition=_game,
        effects={"food_mult": 1.03},
    ),
    Discovery(
        "cultivation",
        "Planting",
        "Seeds spilled by the old midden have come up thicker than anywhere else.",
        "Seed is put in the ground on purpose, and the people return to harvest it.",
        155,
        "land",
        requires=("wild_grain", "seasons"),
        effects={"capacity_mult": 1.8, "food_mult": 1.05},
        forms=(
            Form(
                "family_plots",
                "Each family's own plot",
                "Each family clears, plants and keeps what grows on its own ground.",
                ("diligent", "acquisitive"),
                {"plenty": 6, "cohesion": -3},
            ),
            Form(
                "common_fields",
                "Fields worked in common",
                "The fields belong to everyone; all work them and the harvest is shared out.",
                ("generous", "caring"),
                {"cohesion": 4, "stores_share": 0.1},
            ),
            Form(
                "leaders_fields",
                "The leader's fields",
                "The land is the leader's to give; the people work it and the leader holds "
                "the harvest.",
                ("ambitious", "harsh"),
                {"stores_share": 0.25, "cohesion": -4, "leader_regard": 2},
            ),
        ),
    ),
    Discovery(
        "herding",
        "Herding",
        "The tamed beasts have begun to breed among the people.",
        "Herds are kept, moved with the seasons and culled with care.",
        145,
        "land",
        requires=("taming",),
        effects={"capacity_mult": 1.3, "food_mult": 1.05},
    ),
    Discovery(
        "irrigation",
        "Leading water",
        "In a dry spell, someone dug a channel from the stream to the nearest plants.",
        "Ditches carry water to the fields.",
        170,
        "land",
        requires=("cultivation", "settling"),
        condition=_water,
        effects={"capacity_mult": 1.3},
    ),
    # --- craft ------------------------------------------------------------------
    Discovery(
        "cordage",
        "Twisting cord",
        "Someone has been twisting bark fibres together. The result is surprisingly strong.",
        "Fibre is twisted into cord: snares, slings and carrying nets.",
        50,
        "craft",
        requires=("stone_tools",),
        effects={"food_mult": 1.05},
    ),
    Discovery(
        "hides",
        "Working hides",
        "The hunters argue over how to keep skins from stiffening and rotting.",
        "Hides are scraped, smoked and sewn into clothing and shelter.",
        60,
        "craft",
        requires=("stone_tools",),
        condition=_game,
        effects={"health": 1, "capacity_mult": 1.05},
    ),
    Discovery(
        "dwellings",
        "Lasting shelters",
        "A family spent the whole winter in one place and wishes their shelter had been sturdier.",
        "Shelters of timber, earth and hide that stand for years.",
        90,
        "craft",
        requires=("hides",),
        effects={"health": 1, "capacity_mult": 1.05},
    ),
    Discovery(
        "boats",
        "Boats",
        "A log carried a child across the river, and back again.",
        "Hollowed logs and bound reeds carry people over water.",
        90,
        "craft",
        requires=("cordage",),
        condition=_water,
        effects={"contact_mult": 2.0, "food_mult": 1.03},
    ),
    Discovery(
        "bows",
        "The bow",
        "A maker has been bending sticks and cord, trying to throw a dart further.",
        "The bow sends a dart further and harder than any arm.",
        105,
        "craft",
        requires=("cordage", "hides"),
        effects={"food_mult": 1.05, "raid_mult": 1.5},
    ),
    Discovery(
        "pottery",
        "Fired clay",
        "Clay left too near the fire came out hard as stone.",
        "Fired pots hold water and keep food from damp and vermin.",
        105,
        "craft",
        requires=("fire", "food_keeping"),
        effects={"spoilage": -0.08},
    ),
    Discovery(
        "weaving",
        "Weaving",
        "The cord-makers have been trying to lace their cords into something like a hide.",
        "Cloth woven from fibre or wool.",
        115,
        "craft",
        requires=("cordage",),
        requires_any=("taming", "cultivation"),
        effects={"health": 1, "plenty": 3},
    ),
    # --- lore -------------------------------------------------------------------
    Discovery(
        "remedies",
        "Healing plants",
        "An old woman says she knows which leaves ease a fever. Some believe her.",
        "Leaves, roots and barks that ease pain and fever.",
        60,
        "lore",
        requires=("spirits",),
        effects={"health": 1.5, "plague_mult": 0.8},
    ),
    Discovery(
        "seasons",
        "Reading the seasons",
        "The keepers have noticed the stars return to the same places with the cold.",
        "The turning of the year is read in the stars, so the people move before the seasons do.",
        80,
        "lore",
        requires=("songs",),
        effects={"food_mult": 1.05, "insight_mult": 1.1},
    ),
    Discovery(
        "burial",
        "Rites for the dead",
        "When the old die, the people argue over what should be done for them.",
        "The dead are given rites the whole people keep.",
        50,
        "lore",
        requires=("spirits",),
        forms=(
            Form(
                "graves",
                "Graves kept near camp",
                "The dead are buried close by and visited, so they are never far.",
                ("caring",),
                {"cohesion": 4},
            ),
            Form(
                "to_the_wild",
                "Given back to the wild",
                "The dead are left to the land and the beasts, and the living let them go.",
                ("contemplative",),
                {"cohesion": 2, "lore": 0.4},
            ),
            Form(
                "grave_goods",
                "Riches for the great",
                "The great are buried with their finest things, so their names are remembered.",
                ("ambitious", "acquisitive"),
                {"cohesion": 1, "leader_regard": 2},
            ),
        ),
    ),
    Discovery(
        "festivals",
        "Gatherings and dances",
        "The camps have taken to meeting at the year's turning. It could become something more.",
        "The camps gather at set times to sing, dance and trade news.",
        80,
        "lore",
        requires=("songs", "gifts"),
        effects={"cohesion": 3, "lore": 0.5},
    ),
    Discovery(
        "shrine",
        "A sacred place",
        "There is a place the people return to and speak more quietly in.",
        "A place set apart for the unseen, with someone to keep it.",
        115,
        "lore",
        requires=("burial", "festivals"),
        effects={"cohesion": 3, "lore": 0.5, "title:keeper": "Keeper of the sacred place"},
    ),
    Discovery(
        "marks",
        "Making marks",
        "Someone has been cutting notches in a stick to count the moons.",
        "Notches, knots and painted signs that keep count and carry meaning.",
        130,
        "lore",
        requires=("seasons",),
        requires_any=("exchange", "festivals"),
        effects={"insight_mult": 1.25, "lore": 0.5},
    ),
    Discovery(
        "medicine",
        "The healer's art",
        "The healers have begun to remember which cures worked, and for whom.",
        "Setting bones, cleaning wounds, and cures remembered and taught.",
        155,
        "lore",
        requires=("remedies", "marks"),
        effects={"health": 1.5, "plague_mult": 0.7},
    ),
    # --- kin and custom ---------------------------------------------------------
    Discovery(
        "gifts",
        "Customs of giving",
        "Who owes whom, and for what, has become a constant topic around the fires.",
        "Giving and receiving follow customs everyone knows.",
        60,
        "kin",
        forms=(
            Form(
                "binding_gifts",
                "Gifts that bind",
                "A gift creates a bond; to refuse one, or forget it, is a shame.",
                ("generous", "caring"),
                {"cohesion": 4},
            ),
            Form(
                "feasts",
                "Feasts for renown",
                "The great give great feasts, and are honoured for it.",
                ("ambitious", "indulgent"),
                {"cohesion": 2, "leader_regard": 2},
            ),
        ),
    ),
    Discovery(
        "settling",
        "Staying in one place",
        "Fewer families want to move with the seasons. Some have stopped altogether.",
        "The camps stop moving and become villages.",
        145,
        "kin",
        requires=("dwellings",),
        requires_any=("cultivation", "fishing", "herding"),
        effects={"settled": True, "capacity_mult": 1.2, "plague_mult": 1.2},
    ),
    Discovery(
        "council",
        "How the people decide",
        "With so many people, it is no longer clear who decides, or how.",
        "The way the people choose who leads them, and how decisions are made.",
        115,
        "kin",
        condition=_many(450),
        forms=(
            Form(
                "elders",
                "A council of elders",
                "The old and respected meet and decide together; the first among them speaks for "
                "all.",
                ("contemplative", "caring"),
                {"succession": "council", "title:leader": "First Elder", "cohesion": 2},
            ),
            Form(
                "strongest",
                "The strongest leads",
                "Whoever can hold the people leads them, until someone stronger comes.",
                ("harsh", "ambitious"),
                {"succession": "strongest", "title:leader": "Chief", "leader_regard": 2},
            ),
            Form(
                "lineage",
                "Leadership passes in a family",
                "The leader's eldest child leads after them.",
                ("ambitious", "acquisitive"),
                {"succession": "lineage", "title:leader": "Chief"},
            ),
        ),
    ),
    Discovery(
        "exchange",
        "Exchange",
        "People have started swapping what they make for what others have, and arguing "
        "over what is fair.",
        "Settled ways for one family's surplus to become another's.",
        115,
        "kin",
        requires=("gifts",),
        condition=lambda s: _met_anyone(s) or "settling" in s.nation.known,
        forms=(
            Form(
                "favours",
                "Debts of honour",
                "Whatever is given is remembered and repaid in kind, when it is needed.",
                ("generous", "caring"),
                {"cohesion": 2, "category:favours": "favours owed"},
            ),
            Form(
                "barter",
                "Measured barter",
                "Things are traded for things, by measure and by bargaining.",
                ("diligent", "acquisitive"),
                {"plenty": 4, "category:wares": "wares"},
            ),
            Form(
                "tokens",
                "Tokens of worth",
                "Small things everyone agrees are valuable stand in for anything else.",
                ("acquisitive", "ambitious"),
                {"plenty": 6, "cohesion": -2, "category:tokens": "tokens"},
            ),
            Form(
                "common_store",
                "The common store",
                "Surplus goes to a common store, and the keepers give out what each needs.",
                ("caring", "contemplative"),
                {"stores_share": 0.15, "cohesion": 2},
            ),
        ),
    ),
    Discovery(
        "law",
        "Custom and judgement",
        "A killing has gone unanswered, and the dead man's family is not content.",
        "When harm is done, the people know what must follow.",
        115,
        "kin",
        requires=("council",),
        forms=(
            Form(
                "restitution",
                "Making good",
                "Whoever does harm must make it good to those they harmed.",
                ("generous", "caring"),
                {"cohesion": 3},
            ),
            Form(
                "banishment",
                "Casting out",
                "Whoever breaks the people's ways is driven out.",
                ("harsh",),
                {"cohesion": 2, "plenty": -1},
            ),
            Form(
                "keepers_judge",
                "The keepers judge",
                "Those who keep the old ways decide what the old ways demand.",
                ("contemplative",),
                {"cohesion": 2, "lore": 0.3},
            ),
        ),
    ),
]

DISCOVERIES = {d.id: d for d in DISCOVERY_LIST}

# What someone setting out to work at a stirring idea is trying to find out.
QUESTIONS = {
    "food_keeping": "how food might be made to last",
    "wild_grain": "which grass seeds are worth eating",
    "fishing": "how to catch the fish in the shallows",
    "taming": "whether beasts can be kept",
    "cultivation": "why seeds grow thick by the midden",
    "herding": "how to keep the beasts breeding",
    "irrigation": "how to bring water to the plants",
    "cordage": "what twisted fibre is good for",
    "hides": "how to keep skins supple",
    "dwellings": "how to build a shelter that lasts",
    "boats": "how to cross the water",
    "bows": "how to throw a dart further",
    "pottery": "why the clay by the fire turned hard",
    "weaving": "how to lace cord into cloth",
    "remedies": "which leaves ease a fever",
    "seasons": "what the stars say about the seasons",
    "burial": "what is owed to the dead",
    "festivals": "what the gatherings could become",
    "shrine": "what the quiet place asks of us",
    "marks": "how to keep count without forgetting",
    "medicine": "why some cures work",
    "gifts": "who owes what to whom",
    "settling": "whether to stop moving",
    "council": "who should decide for so many",
    "exchange": "what is a fair swap",
    "law": "what must follow when harm is done",
}
START_KNOWN = ("fire", "stone_tools", "songs", "spirits")
DOMAIN_WEIGHT = {"land": 0.4, "craft": 0.25, "lore": 0.2, "kin": 0.15}
PASSIVE_PICKS = 2  # how many stirring ideas the people's practice feeds each year
TOKEN_WORDS = {"water": "shells", "stone": "polished stones", "other": "beads"}


# --- what is known -------------------------------------------------------------


def effects(state):
    """Every effect of what the people know, combined."""
    out = {}
    for did, form_id in state.nation.known.items():
        d = DISCOVERIES.get(did)
        if d is None:
            continue
        form = d.form(form_id)
        pairs = list(d.effects.items()) + (list(form.effects.items()) if form else [])
        for key, value in pairs:
            if key.startswith(ONE_OFF_PREFIXES):
                continue
            if key.endswith("_mult"):
                out[key] = out.get(key, 1.0) * value
            elif isinstance(value, bool):
                out[key] = out.get(key, False) or value
            else:
                out[key] = out.get(key, 0.0) + value
    return out


def fx(state, key):
    """One combined effect, with its neutral value if nothing known affects it."""
    if key.endswith("_mult"):
        return effects(state).get(key, 1.0)
    return effects(state).get(key, 0)


def is_available(state, d):
    known = state.nation.known
    if d.id in known:
        return False
    if any(r not in known for r in d.requires):
        return False
    if d.requires_any and not any(r in known for r in d.requires_any):
        return False
    return d.condition is None or bool(d.condition(state))


def available(state):
    """What the people could come to know now."""
    return [d for d in DISCOVERY_LIST if is_available(state, d)]


def stirring(state):
    """Available ideas the people have begun to grasp, most advanced first."""
    out = [d for d in available(state) if state.nation.insight.get(d.id, 0) > 0]
    return sorted(out, key=lambda d: -progress(state, d))


def progress(state, d):
    return min(1.0, state.nation.insight.get(d.id, 0) / d.cost) if d.cost else 1.0


def add_insight(state, did, amount):
    nation = state.nation
    nation.insight[did] = nation.insight.get(did, 0.0) + amount * fx(state, "insight_mult")


def ripe(state):
    """Available discoveries with enough insight to be understood."""
    return [d for d in available(state) if state.nation.insight.get(d.id, 0) >= d.cost]


# --- forms ---------------------------------------------------------------------


def people_lean(state, tags):
    """How strongly the people as a whole lean toward these inclinations."""
    adults = [c for c in state.living() if c.age(state.year) >= ADULT_AGE]
    if not adults:
        return 0.0
    return sum(tendencies.affinity(c.tendencies, tags) for c in adults) / len(adults)


def pick_form(state, d, rng):
    """The form a discovery takes when nobody in particular decides: the people's leanings."""
    weights = [math.exp(4 * people_lean(state, f.tags)) for f in d.forms]
    return rng.choices(d.forms, weights)[0].id


def _token_word(state):
    if range_has(state, is_watery):
        return TOKEN_WORDS["water"]
    if range_has(state, lambda t: resource(t, "tool_materials") >= 0.7):
        return TOKEN_WORDS["stone"]
    return TOKEN_WORDS["other"]


def learn(state, did, form_id=""):
    """The people now know this. Returns a line for the chronicle."""
    d = DISCOVERIES[did]
    nation = state.nation
    form = d.form(form_id)
    nation.known[did] = form.id if form else ""
    nation.insight.pop(did, None)
    fx_all = dict(d.effects) | (form.effects if form else {})
    for key, value in fx_all.items():
        if key == "succession":
            nation.succession = value
        elif key.startswith("title:"):
            nation.names[key] = value
        elif key.startswith("category:"):
            category = key.split(":", 1)[1]
            nation.names[category] = _token_word(state) if category == "tokens" else value
    if form:
        return f"[b]{d.name}[/b]: {form.name.lower()}. {form.text}"
    return f"[b]{d.name}[/b]. {d.text}"


def categories(nation):
    """Budget categories in use: the basics, plus whatever exchange has brought."""
    extra = [c for c in ("wares", "tokens", "favours") if c in nation.names]
    return ["food", "hands", "regard"] + extra


def category_name(nation, category):
    return nation.names.get(category, category)


# --- yearly practice ---------------------------------------------------------


def yearly_insight(state, rng):
    """Ordinary life feeds a couple of stirring ideas a little every year."""
    options = available(state)
    if not options:
        return
    nation = state.nation
    amount = (
        0.6 + nation.lore / 60 + 0.4 * (state.total_population() / 250) ** 0.5
    ) / PASSIVE_PICKS
    weights = [DOMAIN_WEIGHT[d.domain] for d in options]
    for _ in range(PASSIVE_PICKS):
        d = rng.choices(options, weights)[0]
        add_insight(state, d.id, amount * rng.uniform(0.5, 1.5))


def progress_word(fraction):
    if fraction >= 0.8:
        return "almost understood"
    if fraction >= 0.5:
        return "taking shape"
    if fraction >= 0.2:
        return "a growing notion"
    return "a faint idea"
