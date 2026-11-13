# DES-XXX: Title

- **Status:** Designed <!-- Designed | In Progress | Done | Dropped -->
- **Area:** <!-- e.g. Sim, UI, World, Balance, Docs, Process -->
- **Created:** YYYY-MM-DD
- **Updated:** YYYY-MM-DD
- **Depends on:** <!-- DES- IDs that must be Done before the gated steps below can start; "None" if none -->
- **Related:** <!-- other DES-/BUG- IDs, PRs, branches -->

## Summary

One or two sentences: what this is and why it matters.

## Motivation / Problem

What problem does this solve? What happens if we don't do it?

## Goals and Non-goals

**Goals**

-

**Non-goals**

-

## Dependencies

Other designs this one needs, what it needs from each, and which steps of the
Implementation Plan they block. Each is its own design and its own stream of
work: never make "design and build DES-xxx" a step of this plan. Delete this
section if there are none.

| Design | What this design needs from it | Blocks |
|---|---|---|

Before starting a gated step, check the backlog: every design listed above
must be **Done**. If any is not, stop and do not start the step.

## Proposed Design

How it works, in prose, tables and diagrams. Name the affected modules
(`sim/`, `ui/`, `world/`), changes to saved state and tunables, and say what
the code will do. Do not put code in a design doc: code lives in code files.

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|

## Implementation Plan

Mark any step that needs a dependency to be Done as **Gated.**

- [ ] Step 1
- [ ] **Gated.** Step 2

## Testing / Verification

How we'll know it works: tests to add, manual checks, commands to run. For a
change to the rules, say what an autoplay balance run should show
(`tests/test_sim/conftest.py::autoplay`: population, cohesion, stores, how fast
discoveries arrive). For a change to anything the player reads, the hidden
words stay hidden (`tests/test_ui.py`).

## Open Questions

-

## Changelog

- YYYY-MM-DD — Created.
