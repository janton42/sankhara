import sys
import os

from sankhara.entities.player import Player
from sankhara.entities.player_state import PlayerState
from sankhara.entities.lineage import Family


class DummyFamily(Family):
    def __init__(self, family_id="fam1", tribe=None):
        super().__init__(family_id, tribe)


def test_playerstate_init():
    state = PlayerState(species="human", age=20, health=80.0, happiness=60.0)
    assert state.species == "human"
    assert state.age == 20
    assert state.health == 80.0
    assert state.happiness == 60.0
    assert state.is_alive()


def test_player_init_and_is_human():
    fam = DummyFamily()
    state = PlayerState(species="human", age=25)
    player = Player(player_id="p1", family=fam, state=state, karma=10.0)
    assert player.player_id == "p1"
    assert player.family is fam
    assert player.state is state
    assert player.karma == 10.0


def test_player_reincarnate():
    fam1 = DummyFamily("fam1")
    fam2 = DummyFamily("fam2")
    state1 = PlayerState(species="human", age=30)
    state2 = PlayerState(species="wolf", age=2)
    player = Player(player_id="p2", family=fam1, state=state1)
    player.reincarnate(new_state=state2, new_family=fam2)
    assert player.state is state2
    assert player.family is fam2


def test_family_add_member_and_relation():
    fam = DummyFamily()
    fam.add_member("p1")
    fam.add_member("p2")
    assert "p1" in fam.members
    assert "p2" in fam.members
    fam.add_relation(("parent", "child"), ("p1", "p2"))
    assert ("parent", "child") in fam.relations
    assert ("p1", "p2") in fam.relations[("parent", "child")]
