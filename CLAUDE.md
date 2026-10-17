# Sankhara

Nation builder without war (Python 3.12, Kivy), played one life at a time: each
turn is a year, the player acts as one character with 3 attention slots and their
station's budget, and on death continues as someone new in the same nation.
Buddhist ideas (karma, rebirth, saṅkhāra) are modelled but never named in-game.
Design: `docs/concepts.md`. Milestone 1 (core loop) is built; M2 = research,
culture, policy, territory; M3 = detailed NPCs and court politics.

## Commands

- `uv run sankhara` — run the game (entry point `sankhara.app:main`)
- `uv run pytest` — tests with coverage (Kivy UI tests need a display; CI uses `xvfb-run`)
- `uv run ruff check .` / `uv run ruff format .` — lint / format (pre-commit runs both)
- `uv run --group docs mkdocs serve` — docs preview

## Layout

- `src/sankhara/sim/`: the game itself, pure Python (no Kivy): `state.py` dataclasses + JSON round-trip, `game.py` yearly loop/new game/next life, `actions.py`, `events.py`, `nation.py` economy, `people.py`, `npc.py`, `tendencies.py`, `stations.py`, `save.py`
- `src/sankhara/ui/`: Kivy only reads state and calls `sim.game` (`options`, `choose`, `affordable`, `remaining_budget`, `end_year`, `begin_next_life`); `words.py` maps numbers to words; `theme.py` palette and widgets
- `src/sankhara/world/`: map generation and `hexgrid.py`; `constants/config.py`: map/biome/culture tunables
- `tests/test_sim/` covers the rules; `tests/test_ui.py` drives the real widgets headless
- `docs/concepts.md` is the user's design doc (authoritative, don't rewrite it); `docs/architecture.md` maps the design to code

## Notes

- Design rules: karma, tendencies and death ages are hidden. Never put the words karma, rebirth, tendency or saṅkhāra (or their numbers) in the UI; `tests/test_ui.py` checks this.
- All randomness in the sim goes through `state.rng()`, so saves replay identically; never use the global `random` there.
- Balance check: autoplay a few hundred years headless (see `tests/test_sim/conftest.py::autoplay`) and look at population, stability, treasury and character counts.
- Tiles are dicts (`id`, `q`=col, `r`=row, `elevation`, `moisture`, `biome`, `abbr`, `resources`); the map is a list of columns, laid out as a pointy-top odd-r hex grid.
- `generate_map(seed)` is deterministic per seed; pass an `rng` rather than using global `random` in generation code.
- To check visuals, drive the app with `Clock.schedule_once` and `Window.screenshot()` to a scratch dir.
- `noise` is an old C extension with no wheels — if it fails to build, swap for `opensimplex`/`pyfastnoiselite`.
- MkDocs is pinned `<2`; Material doesn't support MkDocs 2.0.
