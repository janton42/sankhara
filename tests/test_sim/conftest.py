import random

import pytest

from sankhara.sim import discoveries, game


@pytest.fixture
def state():
    return game.new_game(seed=1234)


def autoplay(state, years, seed=0):
    """Advance a game, picking random affordable options, choosing the shape of new customs
    at random, and starting new lives."""
    rnd = random.Random(seed)
    for _ in range(years):
        if state.pending_choice:
            d = discoveries.DISCOVERIES[state.pending_choice]
            game.choose_form(state, rnd.choice(d.forms).id)
        for slot in range(len(state.plan)):
            if state.plan[slot] is None:
                options = [
                    o
                    for o in game.options(state)
                    if o.key not in state.plan and game.affordable(state, o, slot)
                ]
                if options:
                    game.choose(state, slot, rnd.choice(options).key)
        if game.end_year(state).life_ended:
            game.begin_next_life(state)
    return state


@pytest.fixture
def play():
    return autoplay
