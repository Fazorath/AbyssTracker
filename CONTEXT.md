# AbyssTracker

Tracks ISK made running abyssal deadspace and incursions in EVE Online. All amounts are in millions of ISK, all times in minutes.

## Language

**Run**:
One trip into abyssal deadspace on one filament, logged with its profit and the minutes it took (20 minus the time left on the timer). An incursion site is logged the same way but is called a site.
_Avoid_: trip, pocket (a pocket is one room inside a run)

**Session**:
A stretch of play holding the runs of one kind (abyss or incursion), started with a filament (tier and weather) for abyss. Its total is the sum of its runs' profit.
_Avoid_: batch, sitting

**Active ship**:
The ship EVE says the character is flying at the moment of the read, by its item id.
_Avoid_: current ship, hull

**Cargo**:
The items directly in the active ship's cargo hold (ESI location flag `Cargo`), ammo included. Not the drone bay, fitted modules, loaded ammo, items inside containers, or other ships and hangars.
_Avoid_: inventory, loot, hold contents

**Cargo value**:
What the cargo is worth, priced with CCP's average market price (or the adjusted price when there is no average). Typed by hand from EVE's inventory estimated value, or fetched from ESI.
_Avoid_: loot value, net worth

**Cargo before / Cargo after**:
The cargo value going into a run and coming out of it. Cargo before is prefilled from the previous run's cargo after in the same session, and can be changed when the hold was restocked or unloaded in station. The first run of a session starts with cargo before empty.

**Run profit**:
Cargo after minus cargo before. Filaments and ammo used up come out of it on their own, because they leave the hold. It can be negative, for example after losing cargo. Old runs logged from the wallet keep the profit they were logged with.
_Avoid_: loot, gain, wallet change

**Unpriced item**:
A cargo item type with no market price (for example an abyssal module). It is left out of a fetched cargo value and counted ("· 2 unpriced"), so the user knows the figure is incomplete.

**Wallet**:
The character's ISK balance. Shown on the Abyss page read-only, for reference. It takes no part in run profit any more; the Incursion page still reads payouts from the wallet journal, since those arrive as ISK.
_Avoid_: balance (in UI copy), ISK (as a noun for the wallet)

## Relationships

- A **Session** holds many **Runs**; a **Run** belongs to exactly one **Session**.
- A **Run** is either a cargo run (cargo before and cargo after set, no wallet after) or an old wallet run (wallet after set, no cargo values).
- **Run profit** = **Cargo after** − **Cargo before** for a cargo run.
- A run's **Cargo before** defaults to the previous cargo run's **Cargo after** in the same **Session**.
- **Cargo value** counts only the **Active ship**'s **Cargo**; **Unpriced items** are counted, not valued.

## Example dialogue

> **Dev:** "The user sold nothing this session, so the **Wallet** barely moved. What did run 3 make?"
> **Domain expert:** "Its **Run profit**: the **Cargo after** they typed when they left, minus the **Cargo before** going in. The **Wallet** doesn't come into it."
> **Dev:** "And if they dropped loot in station before run 4?"
> **Domain expert:** "They change run 4's prefilled **Cargo before** to what's left in the hold. Run 3 keeps its profit."

## Flagged ambiguities

- "Loot" was used for both the items picked up in a run and the all-assets "Loot (unsold)" stat from #41. Resolved: the stat is removed, and what a run brings back is measured as **Cargo value**.
- "Wallet" was used for both the ISK balance and a run's starting figure. Resolved: **Wallet** means only the ISK balance; a run starts from **Cargo before**.

_Rebuilt from the decisions recorded in GitHub issue #38 (grilled 2026-10-25); the original working-tree copy was lost before it was committed._
