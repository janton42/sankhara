# Sankhara

Turn-based hex-map world game (Python 3.12, Kivy) modelling Buddhist concepts:
a player is born into a family on a map tile, takes actions each turn that
shift health and karma, and is eventually reborn. Early prototype.

## Commands

- `uv run sankhara` — run the game (entry point `sankhara.app:main`)
- `uv run pytest` — tests with coverage (Kivy UI tests need a display; CI uses `xvfb-run`)
- `uv run ruff check .` / `uv run ruff format .` — lint / format (pre-commit runs both)
- `uv run --group docs mkdocs serve` — docs preview

## Layout

- `src/sankhara/` — package; use absolute `sankhara.*` imports
  - `constants/config.py` — all tunables (noise, thresholds, biomes, resources, hex geometry, `ACTIONS`, `CULTURE_GROUPS`); add new constants here rather than hard-coding
  - `world/` map gen + resources, `core/` engine + turn manager, `entities/` player/family, `ui/` Kivy widgets, `app.py` app wiring
- `tests/` mirrors the package (`test_core/`, `test_world/`, `test_entities/`)
- `docs/` — mkdocs-material site (`mkdocs.yml`); keep `docs/architecture.md` in sync with structural changes

## Notes

- Tiles are dicts (`id`, `q`, `r`, `elevation`, `moisture`, `biome`, `abbr`, `resources`); the map is a list of columns.
- `noise` is an old C extension with no wheels — if it fails to build, swap for `opensimplex`/`pyfastnoiselite`.
- MkDocs is pinned `<2`; Material doesn't support MkDocs 2.0.
