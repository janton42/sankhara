# Architecture

All code lives in the `sankhara` package under `src/`.

| Package | Responsibility |
| --- | --- |
| `sankhara.constants` | `config.py`: every tunable value — noise parameters, map size, biome thresholds and resource baselines, hex geometry, player actions, culture groups. |
| `sankhara.world` | Map generation (`map_gen.py`) and resource extraction/regeneration (`resources.py`). |
| `sankhara.core` | `game_engine.generate_map()` builds the map; `turn_manager` applies end-of-turn resource regeneration and action effects. |
| `sankhara.entities` | `Player`, `PlayerState`, `Family` (lineage) and name generation. |
| `sankhara.ui` | Kivy widgets: the info/action panel (`ui_kivy.py`) and screens (menu, map view, game over). |
| `sankhara.app` | `SankharaApp` and the screen manager wiring; `main()` is the entry point. |

## World generation

1. Perlin noise (`noise` library) produces elevation and moisture grids of
   `MAP_WIDTH × MAP_HEIGHT`, normalised to `[0, 1]`.
2. Each value is bucketed by `ELEVATION_THRESHOLDS` / `MOISTURE_THRESHOLDS`;
   the pair names the biome (e.g. `"Hill Forest"`).
3. Resources are seeded from `BIOME_RESOURCE_BASELINES` with ±
   `RESOURCE_VARIATION_PERCENTAGE` random variation.

The map is a list of columns of tile dicts with `id`, `q`, `r` (axial hex
coordinates), `elevation`, `moisture`, `biome`, `abbr` and `resources`.

## Turn loop

At the end of a turn `process_player_actions()` adds each taken action's karma
and health effects, applies skip penalties for skippable actions not taken, and
clamps karma to `[-1, 1]` and health to `[0, 100]`. `regenerate_resources()`
then regrows renewable resources toward their biome maximum.

## Stubs

`core/karma.py`, `entities/npc.py`, `world/terrain.py` and `world/biomes.py`
are empty placeholders for planned features.
