"""The web of ideas drawn as a graph: what the people know, and what is stirring among
them, laid out left to right by how much must be known first. Nothing beyond what is
stirring is shown, so nothing is spoiled."""

from dataclasses import dataclass, field
from functools import cache

from kivy.graphics import Color, InstructionGroup, Line, Rectangle
from kivy.uix.label import Label
from kivy.uix.relativelayout import RelativeLayout

from sankhara.sim import discoveries
from sankhara.ui.theme import ACCENT, MUTED, PANEL, TEXT

NODE_W = 170
NODE_H = 44
COLUMN_GAP = 56
ROW_GAP = 14
MARGIN = 16
DOMAINS = ("land", "craft", "lore", "kin")
DOMAIN_COLORS = {
    "land": (0.42, 0.62, 0.32, 1),
    "craft": (0.78, 0.55, 0.30, 1),
    "lore": (0.45, 0.58, 0.80, 1),
    "kin": (0.78, 0.42, 0.45, 1),
}
DOMAIN_WORDS = {"land": "the land", "craft": "craft", "lore": "lore", "kin": "kin and custom"}


@dataclass
class Node:
    id: str
    label: str
    known: bool
    progress: float  # how near the people are to it (1 once known)
    depth: int
    domain: str
    row: int = 0
    parents: list = field(default_factory=list)  # what it grew from, among the known
    links: list = field(default_factory=list)  # those of them drawn: the nearest only


@cache
def depth(did):
    """How many ideas deep this one lies: 0 for what needs nothing first."""
    d = discoveries.DISCOVERIES[did]
    before = [depth(r) for r in d.requires]
    if d.requires_any:
        before.append(min(depth(r) for r in d.requires_any))
    return 1 + max(before) if before else 0


@cache
def ancestors(did):
    """Every idea that lies behind this one."""
    d = discoveries.DISCOVERIES[did]
    out = set()
    for r in (*d.requires, *d.requires_any):
        out |= {r} | ancestors(r)
    return frozenset(out)


def _links(n):
    """The parents worth a line: earlier in the web, and not already behind another."""
    return [
        p
        for p in n.parents
        if depth(p) < n.depth and not any(p in ancestors(q) for q in n.parents if q != p)
    ]


def layout(state):
    """The visible ideas as nodes in columns by depth, each column ordered so that ideas
    sit near what they grew from. Returns {id: Node}."""
    known = state.nation.known
    shown = [d for d in discoveries.DISCOVERY_LIST if d.id in known]
    shown += discoveries.stirring(state)
    nodes = {}
    for d in shown:
        is_known = d.id in known
        form = d.form(known.get(d.id, "")) if is_known else None
        if is_known:
            label = d.name + (f": {form.name.lower()}" if form else "")
        else:
            label = discoveries.QUESTIONS.get(d.id, "something new")
        nodes[d.id] = Node(
            d.id,
            label,
            is_known,
            1.0 if is_known else discoveries.progress(state, d),
            depth(d.id),
            d.domain,
            parents=[p for p in (*d.requires, *d.requires_any) if p in known],
        )
    for n in nodes.values():
        n.links = _links(n)
    columns = range(max((n.depth for n in nodes.values()), default=-1) + 1)
    children = {did: [n.id for n in nodes.values() if did in n.links] for did in nodes}
    for sweep in (columns, reversed(columns), columns):
        _order(nodes, sweep, children if sweep is not columns else None)
    return nodes


def _order(nodes, columns, children=None):
    """Order each column by where its neighbours sit: what each idea grew from, or (going
    back) what grew from it. A few such sweeps untangle most crossings."""
    for column in columns:
        here = [n for n in nodes.values() if n.depth == column]

        def place(n):
            near = children[n.id] if children else n.links
            rows = [nodes[o].row for o in near if o in nodes]
            middle = sum(rows) / len(rows) if rows else n.row
            return (middle, DOMAINS.index(n.domain), n.label)

        for row, n in enumerate(sorted(here, key=place)):
            n.row = row


def size_of(nodes):
    columns = max((n.depth for n in nodes.values()), default=0) + 1
    rows = max((n.row for n in nodes.values()), default=0) + 1
    return (
        2 * MARGIN + columns * NODE_W + (columns - 1) * COLUMN_GAP,
        2 * MARGIN + rows * NODE_H + (rows - 1) * ROW_GAP,
    )


class IdeaGraph(RelativeLayout):
    """Draws the graph; choosing a node calls `on_select(node)`."""

    def __init__(self, state, on_select=None, **kwargs):
        self.nodes = layout(state)
        self.on_select = on_select
        self.selected = None
        width, height = size_of(self.nodes)
        super().__init__(size_hint=(None, None), size=(width, height), **kwargs)
        self.drawing = InstructionGroup()  # canvas.before also holds the layout's transform
        self.canvas.before.add(self.drawing)
        self.labels = {}
        for n in self.nodes.values():
            label = Label(
                text=n.label,
                font_size=13 if n.known else 12,
                color=TEXT if n.known else MUTED,
                size_hint=(None, None),
                size=(NODE_W - 12, NODE_H - 6),
                text_size=(NODE_W - 12, NODE_H - 6),
                halign="center",
                valign="middle",
                max_lines=2,
            )
            label.pos = self._box(n)[0][0] + 6, self._box(n)[0][1] + 3
            self.labels[n.id] = label
            self.add_widget(label)
        self.draw()

    def _box(self, n):
        x = MARGIN + n.depth * (NODE_W + COLUMN_GAP)
        y = self.height - MARGIN - NODE_H - n.row * (NODE_H + ROW_GAP)
        return (x, y), (NODE_W, NODE_H)

    def draw(self):
        self.drawing.clear()
        add = self.drawing.add
        lit_last = sorted(
            self.nodes.values(),
            key=lambda n: n.id == self.selected or self.selected in n.links,
        )
        for n in lit_last:
            (x, y), _ = self._box(n)
            for p in n.links:
                if p not in self.nodes:
                    continue
                (px, py), _ = self._box(self.nodes[p])
                a = (px + NODE_W, py + NODE_H / 2)
                b = (x, y + NODE_H / 2)
                mid = (a[0] + b[0]) / 2
                lit = self.selected in (n.id, p)
                if lit:
                    add(Color(*ACCENT))
                else:
                    faint = 0.35 if self.selected or not n.known else 0.7
                    add(Color(*(MUTED[:3]), faint))
                add(Line(bezier=[*a, mid, a[1], mid, b[1], *b], width=2 if lit else 1.1))
        for n in self.nodes.values():
            (x, y), (w, h) = self._box(n)
            tint = DOMAIN_COLORS[n.domain]
            if n.known:
                add(Color(*_mix(tint, PANEL, 0.45)))
                add(Rectangle(pos=(x, y), size=(w, h)))
                add(Color(*tint))
                add(Line(rectangle=(x, y, w, h), width=1.2))
            else:
                add(Color(*PANEL))
                add(Rectangle(pos=(x, y), size=(w, h)))
                add(Color(*(tint[:3]), 0.5))
                add(Line(rectangle=(x, y, w, h), width=1, dash_length=4, dash_offset=3))
                add(Color(*(tint[:3]), 0.8))
                add(Rectangle(pos=(x + 2, y + 2), size=((w - 4) * n.progress, 3)))
            if n.id == self.selected:
                add(Color(*ACCENT))
                add(Line(rectangle=(x - 3, y - 3, w + 6, h + 6), width=2))

    def node_at(self, x, y):
        for n in self.nodes.values():
            (bx, by), (w, h) = self._box(n)
            if bx <= x <= bx + w and by <= y <= by + h:
                return n
        return None

    def select(self, did):
        self.selected = did
        self.draw()
        if self.on_select:
            self.on_select(self.nodes[did])

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        n = self.node_at(*self.to_local(*touch.pos))
        if n is None:
            return False
        self.select(n.id)
        return True


def _mix(color, toward, keep):
    return (*(c * keep + t * (1 - keep) for c, t in zip(color[:3], toward[:3], strict=True)), 1)
