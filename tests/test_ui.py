"""Headless checks of the game UI wired to a real simulation."""

from types import SimpleNamespace

import pytest
from kivy.core.window import Window
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView

from sankhara.sim import discoveries, game
from sankhara.ui import words
from sankhara.ui.game_view import ChooserPopup, FormChoicePopup, GameView, KnowledgePopup
from sankhara.ui.screens.life import LifeScreen
from sankhara.ui.screens.main_menu import ABOUT_TEXT


@pytest.fixture(autouse=True)
def no_leftover_popups():
    """A dismissed pop-up animates away on the clock, which doesn't run here; clear any
    left over so they don't hold the next test's years."""
    yield
    for w in list(Window.children):
        if isinstance(w, ModalView):
            w.dismiss(animation=False)


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


def test_game_view_shows_the_player_and_their_people():
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
        assert opt.name in text
    assert "The people's works" in text and "Your own" in text


def test_hidden_ideas_never_appear_on_screen():
    view, _ = make_view()
    for _ in range(40):
        view.end_year()
        if view.state.life_over:
            game.begin_next_life(view.state)
            view.refresh()
        if view.choice_popup is not None:  # answer it, so it doesn't stay open
            view.choice_popup._choose(
                discoveries.DISCOVERIES[view.state.pending_choice].forms[0].id
            )
    text = (all_text(view) + "\n".join(view.state.log)).lower()
    for word in ("karma", "rebirth", "reincarnat", "tendenc", "sankh"):
        assert word not in text


def test_the_years_keep_passing_through_news():
    view, ended = make_view()
    state = view.state
    start = state.year
    view.toggle_auto()
    assert view.auto_event is not None
    for _ in range(30):
        if ended:
            break
        if state.pending_choice:
            view.choice_popup._choose(discoveries.DISCOVERIES[state.pending_choice].forms[0].id)
        view.auto_step()
    assert state.year > start + 10 or ended
    assert view.year.notices  # news was shown, but the years went on
    assert view.auto_event is not None or ended
    view.stop_auto()


def test_a_year_takes_time_and_waits_for_an_open_window():
    view, _ = make_view()
    state = view.state
    start = state.year
    view.start_auto()
    view._tick(view.year_length / 2)
    assert state.year == start and 0.4 < view.year.bar.value < 0.6
    chooser = ChooserPopup(state, 0, on_pick=lambda: None)
    chooser.open()
    view._tick(view.year_length)
    assert state.year == start  # held while the player looks
    chooser.dismiss(animation=False)
    view._tick(view.year_length)
    assert state.year == start + 1
    view.stop_auto()


def test_pace_can_be_changed():
    view, _ = make_view()
    first = view.year.pace_button.text
    view.change_pace()
    assert view.year.pace_button.text != first


def test_a_new_custom_asks_how_it_should_be():
    view, _ = make_view()
    state = view.state
    d = discoveries.DISCOVERIES["gifts"]
    state.nation.insight[d.id] = d.cost
    state.events = []
    view.end_year()
    assert state.pending_choice == "gifts"
    assert isinstance(view.choice_popup, FormChoicePopup)
    text = all_text(view.choice_popup.content)
    assert all(f.name in text for f in d.forms)
    view.choice_popup._choose("binding_gifts")
    assert state.nation.known["gifts"] == "binding_gifts"
    assert view.choice_popup is None


def test_what_we_know_lists_knowledge_and_peoples():
    view, _ = make_view()
    state = view.state
    n = next(iter(state.neighbours.values()))
    n.met = True
    popup = KnowledgePopup(state)
    text = all_text(popup.content)
    assert "Keeping fire" in text
    assert n.name in text
    near = discoveries.stirring(state)[0]
    assert discoveries.QUESTIONS[near.id] in text
    popup.graph.select(near.id)
    assert near.hint in popup.detail.text


def test_the_idea_graph_shows_only_the_known_and_the_stirring():
    from sankhara.ui import idea_graph

    view, _ = make_view()
    state = view.state
    nodes = idea_graph.layout(state)
    stirring = {d.id for d in discoveries.stirring(state)}
    assert set(nodes) == set(state.nation.known) | stirring
    for n in nodes.values():
        assert n.known == (n.id in state.nation.known)
        assert all(nodes[p].depth < n.depth for p in n.links) and set(n.links) <= set(n.parents)
    hidden = next(d for d in discoveries.DISCOVERY_LIST if d.id not in nodes)
    assert hidden.name not in all_text(idea_graph.IdeaGraph(state))


def test_descriptions_keep_the_game_s_secrets():
    text = ABOUT_TEXT.lower()
    for word in ("win", "karma", "rebirth", "reborn"):
        assert word not in text


def test_those_around_you_are_drawn_and_chosen_with_how_they_feel():
    view, _ = make_view()
    state = view.state
    who, _ = game.around_you(state)[0]
    who.adjust_affinity(state.player_id, 0.9)
    view.refresh()
    graph = view.character.graph
    graph.size = (320, 270)
    shown = {p.id: p for p in graph.people()}
    assert state.player_id in shown and who.id in shown
    p = shown[who.id]
    graph.on_touch_down(SimpleNamespace(pos=(graph.x + p.x, graph.y + p.y)))
    text = view.character.tie_label.text
    assert who.full_name in text and "a friend to you" in text
    assert graph.selected_person == who.id


def test_choosing_someone_shows_their_ties_and_a_camp_brings_the_map_to_it():
    view, _ = make_view()
    state = view.state
    m = view.map_view
    m.size = (600, 450)
    home = state.player.settlement_id
    camp = next(s for s in state.settlements.values() if s.id != home)
    other = next(c for c in state.living() if not c.is_player)
    other.settlement_id = camp.id
    friend = next(c for c in state.living() if c not in (other, state.player))
    friend.adjust_affinity(other.id, 0.9)
    view.on_person(other.id)
    assert m.ties_from == (camp.col, camp.row)
    view.refresh()
    assert m.ties_from == (camp.col, camp.row)
    view.on_person(state.player_id)
    assert m.ties_from is None
    view.on_place(camp.id)
    assert m.zoom > 1 and m.selected_tile is m.map_data[camp.col][camp.row]
    assert view.character.graph.selected_place == camp.id
    assert camp.name in view.tile_label.text


def test_words():
    assert words.feeling_word(-0.8) == "bears you a grudge"
    assert words.health_word(90) == "hale"
    assert words.health_word(5) == "failing"
    assert words.cohesion_word(10) == "torn"
    assert words.food_word(-50, 1000) == "hunger"
    assert words.food_word(50, 1000) == "plenty"
    assert words.population_text(3200) == "3.2k"
    assert words.years_text(3, about=True) == "about 3 years"


def test_the_peoples_works_are_shown_beside_the_map():
    view, _ = make_view()
    state = view.state
    assert "The people's works" in all_text(view)
    from sankhara.sim import projects

    leader = state.leader
    option = next(o for o in projects.options_for(state, leader) if o.definition.common)
    projects.start(state, leader, option)
    view.refresh()
    assert option.name in view.works_label.text


def test_speaking_for_a_custom_when_not_deciding():
    view, _ = make_view()
    state = view.state
    state.pending_choice = "gifts"
    state.pending_mode = "voice"
    view.refresh()
    text = all_text(view.choice_popup.content)
    assert "Speak for" in text
    view.choice_popup._choose("feasts")
    assert "gifts" in state.nation.known


def test_the_map_shows_tribes_ties_and_comes_closer():
    view, _ = make_view()
    state = view.state
    m = view.map_view
    m.size = (600, 450)
    m.draw_map()
    assert [name for name, _ in m.tribes] == [f"the {state.seat.name} folk"]
    home = state.settlement(state.player.settlement_id)
    assert m.names[(home.col, home.row)] == home.name
    m.on_tile_selected(m.map_data[home.col][home.row])
    assert f"the {state.seat.name} folk" in view.tile_label.text
    assert "You live here." in view.tile_label.text
    x, y = m.tile_screen_center(m.selected_tile)
    before = m.hex_size
    m.zoom_at(x, y, 2)
    assert m.hex_size == pytest.approx(before * 2)
    assert m.tile_screen_center(m.selected_tile) == pytest.approx((x, y), abs=1)
    m.zoom_at(x, y, 0.1)
    assert m.zoom == 1.0 and m.pan == (0.0, 0.0)
