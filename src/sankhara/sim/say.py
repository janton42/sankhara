"""Who has a say in what: the matters of a camp reach different people as the people
grow and settle their customs.

In a band every grown person has a voice at the fire. Once there are villages the one
who leads decides who stays and who goes, with the elders if the people keep a council.
Once there are towns no one person decides such things for everyone: the elders of
each camp do, and the leader only for their own. Judging wrongs follows the custom of
law where there is one (the keepers, if the people chose so), else the council, else
the leader.
"""

from sankhara.sim.stations import ADULT_AGE

SCALES = ("band", "village", "town")


def scale(state):
    """How settled the people are: a band of camps, villages, or towns."""
    kinds = {s.kind for s in state.settlements.values()}
    if "town" in kinds:
        return "town"
    if "village" in kinds:
        return "village"
    return "band"


def has_say(state, char, camp_id=None):
    """Whether this person decides the matters of a camp (who stays, who goes)."""
    if char.age(state.year) < ADULT_AGE:
        return False
    size = scale(state)
    if size == "band":
        return True
    camp_id = char.settlement_id if camp_id is None else camp_id
    if char.station == "leader":
        return size == "village" or camp_id == state.seat.id
    council = state.nation.succession == "council"
    return char.is_elder and (council or size == "town") and char.settlement_id == camp_id


def judges(state, char):
    """Whether this person judges wrongs between families."""
    if state.nation.known.get("law") == "keepers_judge":
        return char.station == "keeper"
    if state.nation.succession == "council":
        return char.station == "leader" or char.is_elder
    return char.station == "leader"


def deciders_of(state, camp_id):
    """The tracked people who decide a camp's matters."""
    return [c for c in state.living() if has_say(state, c, camp_id)]
