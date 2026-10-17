"""Saving and loading a game as JSON."""

import json
from pathlib import Path

from sankhara.sim.state import GameState

SAVE_VERSION = 3  # 3: the people's works (shared projects), voices, legacy


def save(state, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": SAVE_VERSION, "state": state.to_dict()}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


def load(path):
    data = json.loads(Path(path).read_text())
    if data.get("version") != SAVE_VERSION:
        raise ValueError(f"Unsupported save version {data.get('version')}")
    return GameState.from_dict(data["state"])
