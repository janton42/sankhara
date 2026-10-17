"""Headless checks of the game UI wired to a real simulation."""

from kivy.uix.label import Label

from sankhara.sim import game
from sankhara.ui import words
from sankhara.ui.game_view import ChooserPopup, GameView
from sankhara.ui.screens.life import LifeScreen


def make_view():
    ended = []
    view = GameView(on_life_ended=ended.append, on_saved=lambda state: None)
    view.set_state(game.new_game(seed=21))
    return view, ended


def all_text(widget):
    texts = []
    for w in widget.walk():
        if isinstance(w, Label):
            texts.append(w.text)
    return "\n".join(texts)


def test_game_view_shows_the_player_and_realm():
    view, _ = make_view()
    state = view.state
    text = all_text(view)
    assert state.player.full_name in text
    assert state.nation.name in text
    assert f"Year {state.year}" in text
    assert view.map_view.territory == {tuple(t) for t in state.nation.territory}


def test_ending_years_advances_and_logs():
    view, ended = make_view()
    start = view.state.year
    for _ in range(3):
        view.end_year()
    assert view.state.year == start + 3
    assert any(line.startswith(f"[b]Year {start + 2}[/b]") for line in view.state.log)
    assert not ended


def test_death_hands_over_to_life_screen():
    view, ended = make_view()
    player = view.state.player
    player.death_age = player.age(view.state.year)
    view.end_year()
    assert ended == [view.state]
    screen = LifeScreen(on_continue=lambda: None, on_begin=lambda: None, on_menu=lambda: None)
    screen.show_death(view.state)
    assert player.full_name in screen.body.text
    lines = game.begin_next_life(view.state)
    screen.show_birth(lines)
    assert "born" in screen.body.text


def test_chooser_lists_every_option():
    view, _ = make_view()
    popup = ChooserPopup(view.state, 0, on_pick=lambda: None)
    text = all_text(popup.content)
    for opt in game.options(view.state):
        assert opt.action.name in text


def test_hidden_ideas_never_appear_on_screen():
    view, _ = make_view()
    for _ in range(40):
        view.end_year()
        if view.state.life_over:
            game.begin_next_life(view.state)
            view.refresh()
    text = (all_text(view) + "\n".join(view.state.log)).lower()
    for word in ("karma", "rebirth", "reincarnat", "tendenc", "sankh"):
        assert word not in text


def test_words():
    assert words.health_word(90) == "hale"
    assert words.health_word(5) == "failing"
    assert words.stability_word(10) == "in turmoil"
    assert words.harvest_word(-50, 1000) == "hunger"
    assert words.harvest_word(50, 1000) == "plenty"
    assert words.population_text(3200) == "3.2k"
    assert words.cost_text({}) == "no cost"
