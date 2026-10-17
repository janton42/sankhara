from sankhara.core import turn_manager


class MockState:
    def __init__(self, health=50.0):
        self.health = health


class MockPlayer:
    def __init__(self, karma=0.0, health=50.0):
        self.karma = karma
        self.state = MockState(health)


def test_process_player_actions_all_taken():
    player = MockPlayer(karma=0.0, health=50.0)
    actions_taken = [a["id"] for a in turn_manager.ACTIONS]
    turn_manager.process_player_actions(player, actions_taken)
    # All positive effects applied, no penalties
    for _a in turn_manager.ACTIONS:
        assert player.karma >= -1 and player.karma <= 1
        assert player.state.health >= 0 and player.state.health <= 100


def test_process_player_actions_all_skipped():
    player = MockPlayer(karma=0.0, health=50.0)
    actions_taken = []
    turn_manager.process_player_actions(player, actions_taken)
    # Only skippable actions apply penalties
    for _a in turn_manager.ACTIONS:
        assert player.karma >= -1 and player.karma <= 1
        assert player.state.health >= 0 and player.state.health <= 100


def test_process_player_actions_mixed():
    player = MockPlayer(karma=0.0, health=50.0)
    # Take first action, skip the rest
    actions_taken = [turn_manager.ACTIONS[0]["id"]]
    turn_manager.process_player_actions(player, actions_taken)
    assert player.karma >= -1 and player.karma <= 1
    assert player.state.health >= 0 and player.state.health <= 100


def test_process_player_actions_clamp():
    player = MockPlayer(karma=0.99, health=99.0)
    # Take all actions to push over max
    actions_taken = [a["id"] for a in turn_manager.ACTIONS]
    turn_manager.process_player_actions(player, actions_taken)
    assert player.karma <= 1
    assert player.state.health <= 100
    # Now test negative clamp
    player = MockPlayer(karma=-0.99, health=1.0)
    # Skip all actions to push below min
    actions_taken = []
    turn_manager.process_player_actions(player, actions_taken)
    assert player.karma >= -1
    assert player.state.health >= 0
