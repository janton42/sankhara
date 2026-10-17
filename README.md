# Sankhara

A nation builder without wars, lived one person at a time. Each turn is a
year; you act as one character with a few slots of attention and your
station's means. When you die the nation carries on, and so do you, as
someone else within it. Built around Buddhist ideas of *saṅkhāra*, karma and
rebirth, which shape the mechanics but are never named in the game. Written in
Python with [Kivy](https://kivy.org).

Status: Milestone 1, the core loop, is playable. See the
[docs](https://janton42.github.io/sankhara/) for the design and roadmap.

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
