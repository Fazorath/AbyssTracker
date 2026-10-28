# Run profit comes from cargo, not the wallet

An abyssal run's profit used to be the change in the character's wallet. The user holds loot for about a month and sells it all at once, so the wallet barely moves during a session and every run showed a profit of about 0. The "Loot (unsold)" stat from #41 valued the net change across all of the character's assets instead, which also picked up market orders, contracts and purchases, was per session rather than per run, and only refreshed hourly.

We decided that a run's profit is the change in the active ship's **cargo value**: cargo after minus cargo before, both typed by the user (or fetched from ESI's asset list, valued at CCP's average price). Filaments and ammo used up leave the hold, so they come out of the profit on their own. The wallet no longer takes part in abyssal runs; it stays on the Abyss page as a read-only figure, and the Incursion page keeps reading payouts from the wallet journal.

## Considered options

- **Keep the wallet** — rejected: it is right only when loot is sold after every run.
- **Value all assets (Loot (unsold))** — rejected: it mixes in unrelated trades and can't attribute value to a single run.
- **Cargo value per run** — chosen: it measures exactly what a run brought back, works signed out, and survives holding loot.

## Consequences

- Runs gain two nullable columns, cargo before and cargo after. The migration only adds them. Old wallet-based runs and sessions are not migrated or recomputed: they keep the profit they were logged with, and a cargo run is told apart from a wallet run by which columns are set. A session left open across the update carries on with cargo runs.
- Editing or deleting a run never re-bases another run, because cargo runs don't chain off each other the way wallet runs did.
- Items without a market price (abyssal modules, for example) can't be valued and are only counted; the user adds them by hand.
- ESI caches assets for up to an hour, so a fetched cargo value can be stale right after a run; the fields stay editable and fetching is a button, not automatic.

_Rebuilt from the decisions recorded in GitHub issue #38 (grilled 2026-10-25); the original working-tree copy was lost before it was committed._
