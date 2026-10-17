# Architecture

All code lives in the `sankhara` package under `src/`.

| Package | Responsibility |
| --- | --- |
| `sankhara.constants` | `config.py`: every tunable value — noise parameters, map size, biome thresholds and resource baselines, player actions, culture groups. |
| `sankhara.world` | Map generation (`map_gen.py`), hex-grid math (`hexgrid.py`) and resource extraction/regeneration (`resources.py`). |
| `sankhara.core` | `game_engine.generate_map(seed)` builds the map; `day_plan` enforces the 24-hour action budget; `turn_manager` applies end-of-day resource regeneration and action effects. |
| `sankhara.entities` | `Player`, `PlayerState`, `Family` (lineage) and name generation. |
| `sankhara.ui` | Kivy widgets: the info/action panel (`ui_kivy.py`), screens (menu, map view, game over), text formatters (`screens/info_panel.py`) and the palette, biome colours and styled widgets (`theme.py`). |
| `sankhara.app` | `SankharaApp` and the screen manager wiring; `main()` is the entry point. |

## World generation

1. Perlin noise (`noise` library) produces elevation and moisture grids of
   `MAP_WIDTH × MAP_HEIGHT`, normalised to `[0, 1]`. Each new game picks a
   random seed (shown in the panel header); the same seed always gives the
   same map. Noise is sampled at each hex's true position so features aren't
   stretched by the offset layout.
2. Each value is bucketed by `ELEVATION_THRESHOLDS` / `MOISTURE_THRESHOLDS`;
   the pair names the biome (e.g. `"Hill Forest"`).
3. Resources are seeded from `BIOME_RESOURCE_BASELINES` with ±
   `RESOURCE_VARIATION_PERCENTAGE` random variation.

The map is a list of columns of tile dicts with `id`, `q` (column), `r` (row),
`elevation`, `moisture`, `biome`, `abbr` and `resources`.

## Hex grid

`world/hexgrid.py` is pure math for a pointy-top grid in "odd-r" offset
coordinates (odd rows shifted half a hex right). `tile_center`,
`pixel_to_tile` (exact, via cube rounding), `hex_corners` and `fit_size` are
all the map view needs: it fits the map to its widget, draws row 0 at the top,
and hit-tests clicks. Biome fill colours come from `theme.biome_color`, which
derives hue from the moisture band and shading from the elevation band.

## Day loop

Each turn is a day. The player fills up to four action slots; `day_plan`
only offers actions that fit in the hours left (24 per day) and respects
non-repeatable actions. On **End Day**, `process_player_actions()` applies each
taken action's karma and health effects (once per occurrence), applies skip
penalties for skippable actions not taken, clamps karma to `[-1, 1]` and health
to `[0, 100]`, and returns the effects, which the panel writes to its log.
`regenerate_resources()` regrows renewable resources toward their biome
maximum. When health reaches 0 the game-over screen shows a summary of the
life.

## Stubs

`core/karma.py`, `entities/npc.py`, `world/terrain.py` and `world/biomes.py`
are empty placeholders for planned features.
