# Backlog

Master index of all design work for Sankhara. Every feature, change to the
rules, view or refactor gets a row here. Bugs are tracked separately in
[buglog.md](buglog.md). The vision itself is in [Concepts](concepts.md).

## How this works

| Phase | Meaning | Individual doc lives in |
|---|---|---|
| Idea | Rough idea; a single row here, no doc yet | — |
| Designed | Design doc written and agreed; not started | `designed/` |
| In Progress | Actively being built | `active/` |
| Done | Built and merged | `archive/` |
| Dropped | Rejected or abandoned after design; kept for the record | `archive/` |

**Conventions**

- **IDs:** `DES-001`, `DES-002`, … — sequential, never reused. Next free ID: **DES-015**.
- **File names:** `<ID>-<kebab-slug>.md`, e.g. `designed/DES-015-many-towns.md`.
- **Promoting an idea:** copy `templates/design-template.md` into `designed/`,
  fill it in, and link it from the row (changing its status to *Designed*).
- **Changing phase:** `git mv` the doc into the new phase's directory, update its
  `Status:` line, update the row's status and link — all in one commit.
- **Dependencies.** When one design needs another to be finished first, the
  dependency goes in the doc's `Depends on:` line and Dependencies section,
  and in the row's *Depends on* column here. The steps it blocks are marked
  as gated; before starting one, check that every listed design is *Done*.
  Another design is never written as a step of a plan.
- **No code in design docs.** A design doc explains what the code will do, in
  prose, tables and diagrams. Code lives in code files.
- **Play-test notes.** Jeff writes them under *Play-test notes* in
  [Concepts](concepts.md), which stays the authoritative design and is not
  rewritten. Each new note becomes an *Idea* row here, or a *Reported* row in
  the [buglog](buglog.md).
- **The game's own rules** hold for every design: what is hidden stays hidden,
  and nothing arrives before the people have found their own form of it. They
  are listed in `CLAUDE.md` under *Notes*.
- **Merging.** Claude's work is done in a git worktree on its own branch off
  `develop` and is committed, pushed and opened as a pull request into
  `develop` by the machine account `janton42-claude`. Jeff reviews and merges;
  Claude never merges. `develop` goes to `main` when Jeff decides.
- **Attribution.** Commits written by Claude are authored by
  `janton42-claude` and carry a `Co-Authored-By: Claude` trailer. Commits
  authored by Jeff are Jeff's own work.

---

## Backlog

Work finished before this system began (DES-002 to DES-012) has a row and no
doc; the *Doc* column gives the pull requests that built it.

| ID | Title | Area | Doc | Depends on | Updated | Status |
|---|---|---|---|---|---|---|
| DES-001 | Design docs system | Process | [doc](archive/DES-001-design-docs-system.md) | — | 2026-11-13 | Done |
| DES-002 | M1, the band: yearly turns, three slots of attention, lives and the next life, hidden karma and inclinations, the people's works, earned leadership, the first web of ideas and their forms, other peoples | Sim, UI | PRs #4–#9 | — | 2026-10-17 | Done |
| DES-003 | M2, policy and government: a second era of ideas (the plough to the town), customs that can be settled anew as a people's work, how the people decide who settles customs, what is owed to the leader, those who fight | Sim | PRs #10, #11 | DES-002 | 2026-10-18 | Done |
| DES-004 | M3, people and politics (first pass): who is around you and how they feel, feuds and grudges that outlive them, rivals, factions and a divided people, matches and marriages, kin by marriage | Sim, UI | PRs #12–#19 | DES-002 | 2026-10-18 | Done |
| DES-005 | M4.1, role and scale: each matter is put to the people it would really reach (who has a say, strangers and newcomers, judging, each food role's own matter, a town's own matters) | Sim | PRs #22, #31 | DES-003, DES-004 | 2026-11-11 | Done |
| DES-006 | M4.2, harm you can start: theft, fights, affairs, killing, blood owed, lies, short measure; weighed by intention, never labelled | Sim | PRs #23, #24 | DES-004 | 2026-10-18 | Done |
| DES-007 | M4.3, neither good nor bad: bride-price, captives, a price for the wrong, ordeal, keeping seed back | Sim | PR #24 | DES-004 | 2026-10-18 | Done |
| DES-008 | M4.4, choices that grow with what the people know: lending and debts with a market, false marks with writing, levies for the wall, the leader's share | Sim | PR #25 | DES-003 | 2026-10-19 | Done |
| DES-009 | M5.1, the web of ideas as a graph: the known and those the people are close to, laid out by depth, nothing beyond | UI | PR #26 | — | 2026-10-19 | Done |
| DES-010 | M5.2, the map as the main view of the people: villages, tribes as regions, where kin, allies and rivals live, where your last life stood | UI, Sim | PR #27 | — | 2026-10-23 | Done |
| DES-011 | M5.3, a small graph centred on you, linked to the map | UI | PRs #28, #29 | DES-010 | 2026-10-23 | Done |
| DES-012 | Only the largest villages become towns | Sim | PR #30 | DES-010 | 2026-10-26 | Done |
| DES-013 | Growing toward an empire: many towns, peoples joined or conquered, distance and rule over it | Sim | | — | 2026-11-13 | Idea |
| DES-014 | Becoming non-human stays out of the main game (perhaps an easter egg) | Sim | | — | 2026-11-13 | Idea |
