# Sankhara

A people over generations (Python 3.12, Kivy), played one life at a time: it
starts as a small band with no farming, trade or money; each turn is a year; the
player acts as one character with 3 attention slots (all optional: answers to
matters at hand, the people's works, or their own cares and undertakings) and their role's means, and on death continues as someone
new among the same people. The years run on a clock the player can pause; only
pop-ups hold it. Leadership is earned, not inherited (unless the people adopt
lineage). Any role can shape the people through the people's works
(shared projects that outlive whoever began them) and by speaking when customs
are settled. Buddhist ideas (karma, rebirth, saṅkhāra) are modelled but
never named in-game, nor in the README, About text or other descriptions, and
nothing says there is no winning. Design: `docs/concepts.md` (check it for new
notes every session). Next: M2 = policy and more development; M3 = detailed NPCs
and politics.

## Commands

- `uv run sankhara` — run the game (entry point `sankhara.app:main`)
- `uv run pytest` — tests with coverage (Kivy UI tests need a display; CI uses `xvfb-run`)
- `uv run ruff check .` / `uv run ruff format .` — lint / format (pre-commit runs both)
- `uv run --group docs mkdocs serve` — docs preview

## Layout

- `src/sankhara/sim/`: the game itself, pure Python (no Kivy): `state.py` dataclasses + JSON round-trip, `game.py` yearly loop/interrupts/new game/next life, `discoveries.py` (the web of ideas and their forms), `projects.py` (multi-year), `actions.py` (one-year deeds: cares and answers), `events.py` (news and matters at hand), `nation.py` (the people's food, stores, cohesion), `people.py`, `peoples.py` (other peoples), `npc.py`, `tendencies.py`, `stations.py` (roles), `save.py`
- `src/sankhara/ui/`: Kivy only reads state and calls `sim.game` (`options`, `choose`, `affordable`, `remaining_budget`, `end_year`, `choose_form`, `begin_next_life`, `threads`); `words.py` maps numbers to words; `theme.py` palette and widgets
- `src/sankhara/world/`: map generation and `hexgrid.py`; `constants/config.py`: map/biome/culture tunables
- `tests/test_sim/` covers the rules; `tests/test_ui.py` drives the real widgets headless
- `docs/concepts.md` is the user's design doc (authoritative, don't rewrite it); `docs/architecture.md` maps the design to code

## Notes

- Design rules: karma, tendencies and death ages are hidden. Never put the words karma, rebirth, tendency or saṅkhāra (or their numbers) in the UI; `tests/test_ui.py` checks this.
- All randomness in the sim goes through `state.rng()`, so saves replay identically; never use the global `random` there.
- Balance check: autoplay a few hundred years headless (see `tests/test_sim/conftest.py::autoplay`) and look at population, cohesion, stores, how fast discoveries arrive (all ~30 should take ~200-300 years) and character counts.
- No era-anachronisms early on: no coin, goods, cities or armies until the people discover their own forms of them; budget categories come from `discoveries.categories()`.
- Tiles are dicts (`id`, `q`=col, `r`=row, `elevation`, `moisture`, `biome`, `abbr`, `resources`); the map is a list of columns, laid out as a pointy-top odd-r hex grid.
- `generate_map(seed)` is deterministic per seed; pass an `rng` rather than using global `random` in generation code.
- To check visuals, drive the app with `Clock.schedule_once` and `Window.screenshot()` to a scratch dir.
- `noise` is an old C extension with no wheels — if it fails to build, swap for `opensimplex`/`pyfastnoiselite`.
- MkDocs is pinned `<2`; Material doesn't support MkDocs 2.0.
