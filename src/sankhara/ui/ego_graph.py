"""The player's own circle drawn as a small graph: them at the centre, the few people their
life turns on around them, gathered inside the camps they live in, and the camps inside
their folk. How someone feels shows in how near they stand and how they are joined, never
as a number. Those who matter little to the player are left out."""

import math
from dataclasses import dataclass, field

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.uix.widget import Widget

from sankhara.sim import game, tribes
from sankhara.ui.theme import ACCENT, BAD, GOOD, MUTED, PANEL, TEXT

NODE = 6  # radius of a person
YOU = 9  # radius of the player
HOME_R = 36  # radius of the player's own camp, alone
PER_NEIGHBOUR = 5  # how much it grows for each of theirs living there
CAMP_R = 22  # radius of another camp holding one person
PER_PERSON = 7  # how much a camp grows for each person beyond the first
GAP = 12  # between the player's camp and the others
FOLK_PAD = 7  # how far a folk's outline stands off its camps
HIT = 11  # how near a click must be to a person to choose them
MARGIN = 10  # around the drawing, and room below a camp for its name
MAX_SCALE = 2.0  # how far a small circle may be enlarged to fill the space


@dataclass
class Person:
    id: int
    name: str
    kind: str  # "you", "family", "kin by marriage", "leader", "close", "against" or "near"
    feeling: float
    camp: int
    x: float = 0.0
    y: float = 0.0


@dataclass
class Place:
    id: int
    name: str
    tribe: int
    x: float = 0.0
    y: float = 0.0
    r: float = CAMP_R
    people: list = field(default_factory=list)


def layout(state, width, height):
    """Places and people, in coordinates within a width x height box. The player's camp
    sits in the middle; the others ring it, the warmer nearer, folk by folk. Laid out at a
    fixed size, then scaled to fill the box."""
    player = state.player
    home_id = player.settlement_id
    groups = game.ties_by_place(state, near=True)
    groups.setdefault(home_id, [])
    places = {}
    for sid, ties in groups.items():
        camp = state.settlement(sid)
        if camp is None:
            continue
        place = Place(sid, camp.name, tribes.tribe_of(state, camp))
        order = {"family": 0, "kin by marriage": 1, "leader": 2}
        for c, kind, feeling in sorted(ties, key=lambda t: (order.get(t[1], 3), -t[2])):
            place.people.append(Person(c.id, c.name, kind, feeling, sid))
        place.r = CAMP_R + PER_PERSON * max(0, len(place.people) - 1)
        places[sid] = place

    cx, cy = width / 2, height / 2
    home = places[home_id]
    home.r, home.x, home.y = HOME_R + PER_NEIGHBOUR * len(home.people), cx, cy
    you = Person(player.id, player.name, "you", 1.0, home_id, cx, cy)
    _ring(home.people, cx, cy, lambda p: home.r * (0.62 - 0.22 * p.feeling))
    home.people.insert(0, you)

    others = sorted(
        (p for p in places.values() if p is not home),
        key=lambda p: (p.tribe != home.tribe, p.tribe, -_warmth(p)),
    )
    for i, place in enumerate(others):
        angle = -2 * math.pi * i / len(others)  # from the right, round the clock
        far = home.r + GAP + place.r + (1 - _warmth(place)) * 10
        place.x, place.y = cx + far * math.cos(angle), cy + far * math.sin(angle)
        if len(place.people) == 1:
            place.people[0].x, place.people[0].y = place.x, place.y
        else:
            _ring(place.people, place.x, place.y, lambda p, r=place.r: r * 0.55, math.pi)
    places = [home, *others]
    _fit(places, width, height)
    return places


def _fit(places, width, height):
    """Scale and centre the drawing in the box (people keep their size, camps grow)."""
    left = min(p.x - p.r for p in places)
    right = max(p.x + p.r for p in places)
    bottom = min(p.y - p.r for p in places) - MARGIN
    top = max(p.y + p.r for p in places)
    scale = min(
        (width - 2 * MARGIN) / (right - left),
        (height - 2 * MARGIN) / (top - bottom),
        MAX_SCALE,
    )
    dx = width / 2 - (left + right) / 2 * scale
    dy = height / 2 - (bottom + top) / 2 * scale
    for place in places:
        place.x, place.y, place.r = place.x * scale + dx, place.y * scale + dy, place.r * scale
        for person in place.people:
            person.x, person.y = person.x * scale + dx, person.y * scale + dy


def _ring(people, x, y, radius, start=math.pi / 2):
    for i, person in enumerate(people):
        angle = start + 2 * math.pi * i / max(1, len(people))
        r = radius(person)
        person.x, person.y = x + r * math.cos(angle), y + r * math.sin(angle)


def _warmth(place):
    return sum(p.feeling for p in place.people) / len(place.people) if place.people else 0.0


def folks(state, places):
    """The folks the shown camps belong to, each as (name, its places), when the people
    have more than one folk; otherwise there is nothing to tell apart."""
    if len(tribes.tribes(state)) < 2:
        return []
    out = {}
    for place in places:
        out.setdefault(place.tribe, []).append(place)
    return [(tribes.tribe_name(state, tid), members) for tid, members in out.items()]


def outline(places, pad=FOLK_PAD, steps=24):
    """A closed outline around some camps: the convex hull of their circles, padded."""
    points = [
        (
            p.x + (p.r + pad) * math.cos(2 * math.pi * k / steps),
            p.y + (p.r + pad) * math.sin(2 * math.pi * k / steps),
        )
        for p in places
        for k in range(steps)
    ]
    return _hull(points)


def _hull(points):
    points = sorted(set(points))
    if len(points) < 3:
        return points

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def tie_color(feeling):
    """Warm ties lean green, cold ones red, slight ones stay muted."""
    keep = 1 - min(1.0, abs(feeling) * 1.5)
    toward = GOOD if feeling >= 0 else BAD
    return tuple(m * keep + t * (1 - keep) for m, t in zip(MUTED[:3], toward[:3], strict=True))


class EgoGraph(Widget):
    """Draws the player's circle and reports clicks: on a person (`on_person(id)`) or on a
    camp (`on_place(settlement id)`)."""

    def __init__(self, on_person=None, on_place=None, **kwargs):
        super().__init__(**kwargs)
        self.on_person = on_person
        self.on_place = on_place
        self.state = None
        self.places = []
        self.folks = []
        self.selected_person = None
        self.selected_place = None
        self._texts = {}
        self.bind(pos=self.draw, size=self.draw)

    def show(self, state):
        self.state = state
        self.draw()

    def people(self):
        return [p for place in self.places for p in place.people]

    def select_person(self, cid):
        self.selected_person = cid
        self.draw()

    def select_place(self, sid):
        self.selected_place = sid
        self.draw()

    # --- drawing ------------------------------------------------------------------

    def draw(self, *_):
        self.canvas.clear()
        if self.state is None or self.width < 10 or self.height < 10:
            return
        self.places = layout(self.state, self.width, self.height)
        self.folks = folks(self.state, self.places)
        ox, oy = self.pos
        with self.canvas:
            Color(*PANEL)
            Rectangle(pos=self.pos, size=self.size)
            for name, members in self.folks:
                hull = outline(members)
                Color(*MUTED[:3], 0.5)
                Line(
                    points=[v for x, y in hull for v in (ox + x, oy + y)],
                    close=True,
                    width=1,
                    dash_length=3,
                    dash_offset=3,
                )
                top = max(hull, key=lambda v: v[1])
                self._label(name, ox + top[0], oy + min(top[1] + 2, self.height - 8), MUTED)
            for place in self.places:
                chosen = place.id == self.selected_place
                Color(*(ACCENT if chosen else (*MUTED[:3], 0.7)))
                Line(circle=(ox + place.x, oy + place.y, place.r), width=2 if chosen else 1)
                self._label(place.name, ox + place.x, oy + place.y - place.r - 7, MUTED)
            you = self.places[0].people[0]
            for person in self.people()[1:]:
                self._edge(you, person)
            for person in self.people():
                self._node(person)

    def _edge(self, you, person):
        ox, oy = self.pos
        points = [ox + you.x, oy + you.y, ox + person.x, oy + person.y]
        chosen = person.id == self.selected_person
        Color(*(ACCENT[:3] if chosen else tie_color(person.feeling)), 0.9)
        if person.feeling < 0:
            Line(points=points, width=1.2, dash_length=4, dash_offset=3)
        else:
            Line(points=points, width=1 + 1.5 * person.feeling + (0.5 if chosen else 0))

    def _node(self, person):
        ox, oy = self.pos
        x, y = ox + person.x, oy + person.y
        r = YOU if person.kind == "you" else NODE
        Color(*PANEL)
        Ellipse(pos=(x - r - 2, y - r - 2), size=(2 * r + 4, 2 * r + 4))
        if person.kind == "you":
            Color(*ACCENT)
        elif person.kind in ("family", "kin by marriage"):
            Color(*(TEXT if person.kind == "family" else MUTED))
        else:
            Color(*tie_color(person.feeling), 1)
            Line(circle=(x, y, r - 1), width=1.6)
            r = 0
        if r:
            Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
        if person.id == self.selected_person:
            Color(*ACCENT)
            Line(circle=(x, y, NODE + 4), width=1.5)
        if person.kind != "you":
            self._label(person.name, x, y - NODE - 8, TEXT)

    def _label(self, text, x, y, color):
        key = (text, color)
        if key not in self._texts:
            label = CoreLabel(text=text, font_size=11, color=color)
            label.refresh()
            self._texts[key] = label.texture
        texture = self._texts[key]
        w, h = texture.size
        Color(*PANEL[:3], 0.7)
        Rectangle(pos=(x - w / 2 - 2, y - h / 2), size=(w + 4, h))
        Color(1, 1, 1, 1)
        Rectangle(texture=texture, pos=(x - w / 2, y - h / 2), size=texture.size)

    # --- touch --------------------------------------------------------------------

    def person_at(self, x, y):
        ox, oy = self.pos
        near = [(math.hypot(ox + p.x - x, oy + p.y - y), p) for p in self.people()]
        near = [(d, p) for d, p in near if d <= HIT]
        return min(near, key=lambda t: t[0])[1] if near else None

    def place_at(self, x, y):
        ox, oy = self.pos
        inside = [p for p in self.places if math.hypot(ox + p.x - x, oy + p.y - y) <= p.r]
        return min(inside, key=lambda p: p.r) if inside else None

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or self.state is None:
            return super().on_touch_down(touch)
        person = self.person_at(*touch.pos)
        if person is not None:
            self.select_person(person.id)
            if self.on_person:
                self.on_person(person.id)
            return True
        place = self.place_at(*touch.pos)
        if place is not None:
            self.select_place(place.id)
            if self.on_place:
                self.on_place(place.id)
            return True
        return super().on_touch_down(touch)
