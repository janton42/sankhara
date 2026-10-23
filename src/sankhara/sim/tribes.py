"""Tribes: clusters of the people's camps that share descent. The first camps are one
tribe; a camp founded from another joins its source's tribe, or failing that the nearest
tribe with room, unless none lies near, and then it begins a tribe of its own. Tribes are
named after the camp they began in."""

from sankhara.world.hexgrid import distance

TRIBE_CAMPS = 5  # camps a tribe holds before new ones begin their own
TRIBE_REACH = 3  # how far a new camp may lie from the nearest of its tribe's camps


def tribe_of(state, camp):
    """The id of the camp a tribe began in (camps from before tribes were kept belong to
    the oldest)."""
    return camp.tribe or min(int(k) for k in state.settlements)


def tribes(state):
    """{tribe id: its camps}."""
    out = {}
    for camp in state.settlements.values():
        out.setdefault(tribe_of(state, camp), []).append(camp)
    return out


def tribe_name(state, tribe_id):
    first = state.settlement(tribe_id)
    return f"the {first.name} folk" if first else "the people"


def found(state, camp, source):
    """A camp founded from `source` takes its place among the tribes: its source's tribe
    if that has room and lies near, otherwise the nearest tribe that does, otherwise a
    tribe of its own. Returns a line if it begins one."""
    camp.founded_from = source.id
    here = (camp.col, camp.row)
    open_to = []
    for tid, kin in tribes(state).items():
        kin = [c for c in kin if c is not camp]
        if not kin or len(kin) >= TRIBE_CAMPS:
            continue
        near = min(distance((c.col, c.row), here) for c in kin)
        if near <= TRIBE_REACH:
            open_to.append((tid != tribe_of(state, source), near, tid))
    if open_to:
        camp.tribe = min(open_to)[2]
        return ""
    camp.tribe = camp.id
    return f"The families of {camp.name} count themselves a folk of their own."
