# Sankhara

A game about a people, from a small band at their first fires to whatever
they become, lived one person at a time. Each turn is a year; you act as one
character with a few slots of attention and the means of your place among the
people. Inspired by Buddhist thought. Written in Python with
[Kivy](https://kivy.org).

Status: early and playable. See the [docs](https://janton42.github.io/sankhara/)
for the roadmap.

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run sankhara
```

## Development

```bash
uv run pre-commit install   # once
uv run pytest               # tests + coverage
uv run ruff check .         # lint
uv run ruff format .        # format
uv run --group docs mkdocs serve   # docs at http://127.0.0.1:8000
```

See [`docs/`](docs/) for concepts, architecture and development notes.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
