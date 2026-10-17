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


## Updated design direction:


Design summary

Premise. A nation builder with no focus on war or armies. Play centers on resource management, policy and government, and scientific and cultural development. Buddhist ideas (saṅkhāra, karma, rebirth) are modeled in the mechanics but never named or highlighted. There is no win condition, and the game runs until the player stops.

Turn structure. One turn is one year. The player acts as the current character, not as an abstract manager of the nation. Each turn has two layers: a fixed number of action slots (about 2 to 3) representing personal attention, and a coarse resource budget (a few categories) representing the nation’s capacity, which actions spend. Karma attaches only to the action layer: which actions are chosen and which obligations are skipped. Budget allocation affects the nation but not karma.

Events. Each year brings events, some random and some driven by the nation’s state. No attempt is made at fairness. Outcomes can be unjust or pointless. Events are the main source of obligations, and skipping them is penalized in karma. Karma tracks intention and choice, never outcomes.

Lifespan and lineage. A character’s life runs roughly 20 to 50 turns with a randomized death age, so the player cannot time final decisions. A full game spans several hundred turns and roughly 6 to 12 lives. Succession and lineage matter, as in Europa Universalis leaders.

Karma. Karma is a hidden score clamped to [-1, 1], never displayed as a number or label. Its only visible effects are felt ones.

Rebirth. Rebirth always stays within the same nation. Social station at rebirth is random, so players are not guaranteed to be rulers, and rank is not part of the karmic ledger at all. Every station has the same size of action set, with differing kinds and scopes of influence: a ruler’s is broad and slow, while a farmer’s or merchant’s is local and immediate. The design deliberately takes the position that status says nothing about worth. Karma governs the conditions within the station: mainly internal (tendencies), with smaller material (health, wealth within the station, family stability) and relational (parents, spouse, advisors, friends) adjustments. Becoming non-human is excluded from the main game, possibly reserved for an easter egg.

Tendencies (saṅkhāra). The past life’s habitual choices become the next life’s default impulses. They are never shown as labels or a character sheet and are only felt through the interface: some actions are cheaper in attention or resources, more prominent or tempting, or carry friction. The effect is a mild-to-moderate nudge that can always be overridden at a small extra cost. Effects must be consistent enough to be learnable. Tendencies shift throughout life at a constant rate: repetition strengthens them and acting against them weakens them, and the pattern at death is what carries into the next life.

NPCs. NPCs use the same model in simplified form, with tendencies that shift based on coarsely simulated choices. Rulers, heirs, advisors, and people near the player or in positions of power are tracked in detail, and the rest are handled statistically. Because rebirth stays in one nation, the people the player influenced remain, and the player can be reborn into the consequences of how they treated and shaped them.


## Updates after first play through (basic UI done from Milestone 1)
No descriptions of the game, including "about" sections or subtitles, should
give away the "punchline" of their being "no winning". That's a huge spoiler,
so it should never be explicit. Similarly, the karma mechanism should not be
explicitly stated. Starting @ 20 is acceptable for now, but the civilization
is far too advanced. It needs to start much further back without so many modern
assumptions applied. There should not yet be coin money or "goods" to be traded.
Imagine the first tribe of people that became modern humans that walked out of Africa,
that's where you start, but not in Africa. It should be a small tribe, max 1,500,
with no clear economic system, no farming, nothing but some oral traditions,
superstitions/religius beleifs, names, language, but socially very early in
their development. Currency, trade, cities, all of that needs to be discovered,
designed, developed. But I don't want it to be prescribed as coming out the way
things are now in the real world (e.g. coins, banks, etc.). This game should be more
fluid than that, and play more like a simulation of human society over generations that
a player can influence through their decisions. War is specifically deprioritized,
so nothing about combat or armies to start, but that is something that will need to be addressed,
becuase violence is real, and I want some aspects of it in the game. It can't be the focus, though.

A separate design effort needs to be made for the attention choices. They're okay to
start, and as fillers, but this needs some close attention.

There should be multi-year projects with interupting events every few years, instead of
having to manually choose minutia events each year. Similar to the mechanism in civilization
with research, or building, or whatever taking a few turns, and if "auto end turn" is
selected, the game runs the plan until something (e.g. disaster, other player)
interrupts.

Much of the development mechanism should be like Civilization, which is an excellent game,
but there's way too much of a focus on combat. The development mechanisms, though, are
very good and should be thought of as a guide for Sankhara.
