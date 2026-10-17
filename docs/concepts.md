# Concepts

The game's mechanics are meant to model a handful of Buddhist ideas. This page
is a skeleton to be expanded from the original design conversation.

## Saṅkhāra

Mental formations or volitional impulses: one of the five aggregates and the
second link of dependent origination. In the game, the accumulated effect of a
character's choices.

## Karma

Intentional action and its consequences. Each turn's actions (and skipped
obligations) adjust a karma score clamped to `[-1, 1]`; see `ACTIONS` in
`sankhara/constants/config.py`.

## Rebirth and lineage

A player is born into a `Family` on a home tile, which determines their culture
group and names. `Player.reincarnate()` swaps in a new state (and optionally a
new family); how karma drives rebirth is still to be designed.

## Open questions

- How karma maps to the next birth (species, family, location).
- Whether NPCs share the same karma model.


## User Notes
- Original conversation is lost.
- The game overall is supposed to be a nation builder that does not focus
on war and army building. It's supposed to be a strategy game with resource
mangament, policy/government management, scientific and cultural development
but without armies and war being the main goal.
- The Karma and rebirth cycle was inspired by the mechanics of the leader in games
like Europa Universalis, in which the player is in charge of a country, but the leaders
are born and die throughout the game, and lineage is an import aspect of holding power.
