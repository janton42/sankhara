# Sankhara

Sankhara is a turn-based world game played on a procedurally generated hex map.
You are born into a family on a tile of the world, act each turn, and those
actions shape your health and karma — and, eventually, what you are reborn as.

The name comes from the Pali *saṅkhāra*: the mental formations and volitional
impulses that, in Buddhist thought, condition what comes next. See
[Concepts](concepts.md).

!!! note "Status"
    Early prototype. Map generation, resources, a basic player/family model and
    turn actions exist; karma, NPCs and terrain are still stubs.

## Running

```bash
uv sync
uv run sankhara        # or: uv run python -m sankhara
```

From the main menu choose **New Game**, click a tile to inspect it, and use the
info panel to start a life and take actions.
