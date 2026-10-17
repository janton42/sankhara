# Architecture

All code lives in the `sankhara` package under `src/`. The game is split into a
pure-Python **simulation** (`sankhara.sim`, no Kivy, fully unit-tested and
saveable) and a **UI** (`sankhara.ui`) that only reads state and calls a handful
of game functions.

| Package | Responsibility |
| --- | --- |
| `sankhara.sim` | The game: state, rules, the yearly loop, lives and save/load. |
| `sankhara.world` | Map generation (`map_gen.py`) and hex-grid math (`hexgrid.py`). |
| `sankhara.core` | `game_engine.generate_map(seed)` builds the terrain. |
| `sankhara.entities` | Name generation per culture (`namer.py`). |
| `sankhara.ui` | Kivy screens: menu, game view, between-lives screen; `theme.py` palette and widgets; `words.py` turns numbers into the words the player sees. |
| `sankhara.constants` | `config.py`: map size, noise, biome thresholds and resources, culture groups. |
| `sankhara.app` | `SankharaApp`: screen flow and autosave. |

## How the design maps to code

The design lives in [Concepts](concepts.md). Milestone 1 implements the core
loop:

| Design | Implementation |
| --- | --- |
| One turn is one year | `game.end_year()` advances the world one year, then `begin_year()` sets up the next. |
| 2–3 action slots of personal attention | `stations.ACTION_SLOTS = 3`; `game.options()`, `choose()`. |
| A coarse budget the actions spend | `Budget(food, goods, coin)`. Rulers spend the national treasury; everyone else their household (`actions.budget_for`). |
| Karma only on the action layer | Each `Action` has a hidden `karma` value for its intention; skipped obligations subtract `EventInstance.penalty`. Outcomes never touch it. Stored on `Soul.karma`, clamped to [-1, 1]. |
| Events, some random, some state-driven, not fair | `events.EVENTS`: drought, plague, famine (when settlements go hungry), unrest (low stability), sick relatives, strangers… Meeting an obligation guarantees nothing. |
| Lives of 20–50 turns, random death age | `Character.death_age` is hidden: 16 + 20..50. Health can end a life sooner. |
| Rebirth in the same nation, random station | `game.begin_next_life()`: station drawn by `Station.rebirth_weight`; childhood is fast-forwarded to age 16. |
| Karma shapes conditions, not rank | At rebirth karma tilts carried-over tendencies (`tendencies.carry_into_next_life`), health, `fortune` (income), `family_stability` (family misfortune), parents' warmth, and which existing couple you are born to. Half of it is spent doing so. |
| Tendencies, felt not shown | `tendencies.py`: choosing an action strengthens its tags; declining a habitual default weakens them. Inclinations change costs (±30%), the order options appear in, their tint in the chooser, and which actions are pre-filled each year. |
| NPCs, same model simplified | `npc.py`: tracked adults choose station actions by tendency (rulers also by the realm's needs). Rulers' and nobles' choices act on the world. Upbringing and counsel pull others' tendencies toward the player's. |
| Succession and lineage | `people.succeed()`: eldest child, then sibling; if the line fails, an advisor founds a new house. |
| No win condition | The game runs until the player stops; it autosaves every year. |

## Simulation modules

- **`state.py`**: dataclasses (`GameState`, `Nation`, `Settlement`, `Character`, `Soul`, `Budget`, `EventInstance`) with `to_dict`/`from_dict`. The RNG state is saved too, so a loaded game plays on identically.
- **`game.py`**: founding a nation (capital on fertile interior land, a realm of radius 2, a few villages, a newly crowned ruler as the first life), the yearly loop, death and the next life.
- **`actions.py`**: about 45 actions across six stations, plus generic and obligation-only actions. Each has a cost, tags, hidden karma and an effect function.
- **`events.py`**: event definitions, yearly generation, obligation resolution.
- **`nation.py`**: settlement economy (harvest falls as land fills up, taxes, hunger, growth), treasury upkeep and spoilage, drift of stability and prosperity, learning and arts with diminishing returns, household income and upkeep.
- **`people.py`**: creating characters, families, ageing, marriage and births (tracked only for the ruler's line and the player's family), succession, keeping the court staffed.
- **`stations.py`**, **`tendencies.py`**, **`npc.py`**, **`world.py`** (cached map per seed, fertility), **`save.py`** (JSON).

## World generation

1. Perlin noise produces elevation and moisture grids of `MAP_WIDTH × MAP_HEIGHT`,
   sampled at each hex's true position and normalised to `[0, 1]`. The game
   seed fixes the map.
2. Each value is bucketed by `ELEVATION_THRESHOLDS` / `MOISTURE_THRESHOLDS`;
   the pair names the biome (e.g. `"Hill Forest"`).
3. Resources are seeded from `BIOME_RESOURCE_BASELINES`; a tile's fertility
   (plant food, animal food, fresh water) drives harvests.

## Hex grid

`world/hexgrid.py` is pure math for a pointy-top grid in "odd-r" offset
coordinates: centres, exact pixel-to-tile picking, corners, neighbours,
distance and fitting a map to a box. The map view dims land outside the realm,
outlines its border, marks settlements (capital in saffron) and outlines the
player's home.
