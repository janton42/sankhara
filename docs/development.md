# Development

Requires [uv](https://docs.astral.sh/uv/). The project is pinned to Python 3.12
(`.python-version`); uv will download it if needed.

```bash
uv sync                     # create .venv with runtime + dev dependencies
uv run pre-commit install   # run ruff and basic checks on every commit
```

## Common commands

| Task | Command |
| --- | --- |
| Run the game | `uv run sankhara` |
| Tests (with coverage) | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| All pre-commit hooks | `uv run pre-commit run --all-files` |
| Docs preview | `uv run --group docs mkdocs serve` |

## Tests

Tests live in `tests/`, mirroring the package layout (`test_core/`,
`test_world/`, …). `tests/conftest.py` sets `KIVY_NO_ARGS` so Kivy doesn't
consume pytest's arguments. UI tests need a display; CI runs them under
`xvfb-run`.

## CI

GitHub Actions runs lint and tests on every push and pull request
(`.github/workflows/ci.yml`), and publishes these docs to GitHub Pages on
pushes to `main` (`.github/workflows/docs.yml`).
