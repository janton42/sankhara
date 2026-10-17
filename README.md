# Sankhara

A turn-based world game on a procedurally generated hex map, built around
Buddhist ideas of *saṅkhāra* (volitional formations), karma, rebirth and
lineage. Written in Python with [Kivy](https://kivy.org).

Early prototype: map generation, resources, a basic player/family model and
turn actions are in place.

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
