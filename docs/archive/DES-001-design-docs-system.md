# DES-001: Design docs system

- **Status:** Done
- **Area:** Process
- **Created:** 2026-11-13
- **Updated:** 2026-11-13
- **Depends on:** None
- **Related:** branch `design-docs`

## Summary

A two-layer documentation system in `docs/`, the same one hl_vae and localtools
use: index files that list every item by phase, plus one design doc per item,
filed in a directory that matches its phase. It replaces `docs/plan.md`.

## Motivation / Problem

All work was tracked in one file, `docs/plan.md`: a list of milestones with a
paragraph each, marked "built" as they landed. That was enough for M1 to M5,
but it gave a design no room of its own, had no place for bugs, and worked
differently from Jeff's other projects.

## Goals and Non-goals

**Goals**

- One place to see all work at a glance, with its phase.
- Bugs tracked in a separate index with the same format.
- Every item past the rough-idea phase has its own doc, in a directory that
  matches its phase.
- The same layout, templates and conventions as hl_vae and localtools.

**Non-goals**

- Replacing [Concepts](../concepts.md). It stays the authoritative design and
  the place for play-test notes.
- Writing design docs after the fact for what is already built.
- Tooling or automation. This is plain Markdown in git.

## Proposed Design

**Layer 1: index files**

- [`docs/backlog.md`](../backlog.md) lists design work with its status: Idea,
  Designed, In Progress, Done or Dropped.
- [`docs/buglog.md`](../buglog.md) lists bugs in the phases Reported, Triaged,
  Fixing and Closed.

**Layer 2: per-item docs**

```
docs/
├── backlog.md
├── buglog.md
├── designed/        # DES docs: designed, not started
├── active/          # DES docs: in progress
├── archive/         # DES docs: done or dropped
├── bugfixes/
│   ├── open/        # BUG docs: triaged or fixing
│   └── closed/      # BUG docs: fixed or won't fix
└── templates/
    ├── design-template.md
    └── bugfix-template.md
```

Ideas and new bug reports are a single row in the index, with no doc yet.

**Conventions** are written out in the two index files: sequential IDs that
are never reused, `<ID>-<kebab-slug>.md` file names, a phase change as one
commit (`git mv`, the `Status:` line, the row), dependencies and gated steps,
no code in design docs, and how work is merged and attributed.

**What is particular to Sankhara**

- The templates come from localtools. The Area examples are Sankhara's, and
  the design template's verification section points at the autoplay balance
  run and the hidden-words test.
- Work built before this system (M1 to M5 and towns) is a *Done* row each,
  with pull request numbers in place of a doc. The text of `plan.md` is in
  those rows; the file is removed.
- Play-test notes still arrive in `concepts.md`; each becomes a row.
- The docs site publishes the two indexes, linked from the navigation, and
  the per-item docs, reached from their rows. Templates are not published
  (MkDocs leaves `templates/` out by default).

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Keep `plan.md` beside the backlog | No history moved | Two places that say what is done and what is next | One index is the point |
| A design doc for each built milestone | Complete archive | About a dozen docs reconstructed from memory and git | Rows with pull requests say as much |

## Implementation Plan

- [x] Create `backlog.md` and `buglog.md`
- [x] Create phase directories (with `.gitkeep`)
- [x] Add design and bugfix templates
- [x] Seed the backlog from `plan.md`, then remove `plan.md`
- [x] Update the docs navigation, `index.md`, `architecture.md` and `CLAUDE.md`

## Testing / Verification

- `find docs -type f | sort` matches the layout above.
- `uv run --group docs mkdocs build --strict` passes.
- No link to `plan.md` remains.

## Open Questions

- None.

## Changelog

- 2026-11-13 — Created and implemented.
