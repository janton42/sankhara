# Sankhara

Sankhara is a nation builder without wars, lived one person at a time. Each
turn is a year. You act as one character, with a few slots of attention and
whatever budget your station gives you: the treasury if you rule, your
household if you farm, trade or teach. Events arrive, some of them asking
something of you. When you die, the nation carries on and you begin again
somewhere within it.

The ideas behind it are in [Concepts](concepts.md); how they are built is in
[Architecture](architecture.md).

!!! note "Status"
    Milestone 1 (the core loop) is playable: yearly turns, six stations,
    events and obligations, lives, succession and continuing in a new life.
    Research, policy and territorial growth come in Milestone 2; detailed
    NPC relationships and court politics in Milestone 3.

## Running

```bash
uv sync
uv run sankhara        # or: uv run python -m sankhara
```

Choose **New Game**. Click a slot under *Your attention* to decide what the
year is for, then **End the Year**. The game saves itself every year;
**Continue** picks up where you left off.
