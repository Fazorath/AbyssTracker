# Abyssal and Incursion Tracker

A desktop tracker for EVE Online pilots who run abyssal deadspace and incursions: profit per run, ISK/hour, an abyss timer, and a small pocket window that sits beside the EVE client.

> Not affiliated with abysstracker.com. This is a local desktop app.

**[Download for Windows or Apple Silicon](https://github.com/Fazorath/AbyssTracker/releases/latest)** (no Python needed)

![Abyss page with a live session, the abyssal timer and the run log](docs/screenshots/abyss.png)

<!-- GIF: pocket mode beside the client, run detection starting the timer, logging a run. Not recorded yet. -->

## Contents

- [Features](#features)
- [What it reads from your character](#what-it-reads-from-your-character)
- [How profit works](#how-profit-works)
- [Known limits](#known-limits)
- [Screenshots](#screenshots)
- [Getting started](#getting-started)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Features

**Desktop app (`gui.py`):**
  - **Session page:** pick the filament's weather and tier, then log each run with its cargo value before and after and the time left on the 20-minute timer. The large abyssal countdown can fill in the time for you
    (leave the field blank). The page takes the colours of the session's weather and shows its tactical hint.
  - **Incursion page:** set the payout per site (remembered between sessions) and log each site's time, typed or
    from the built-in stopwatch.
  - Each run shows as a tile with its profit, duration and **ISK/hour**, where you can fix (✎) or delete mistakes,
    with the session's profit, ISK/hour, time below.
  - **History page:** net profit, ISK/hour and winning sessions, a profit-per-session chart with hover details,
    ISK/hour for each weather (and the best one), and every past session with its weather and tier,
    filterable by Abyss/Incursion. Old `Sessions.txt` files can be imported, the current filter can be exported to CSV, and `tracker.db` can be backed up and restored with a click.
  - **Pocket mode:** a small always-on-top window to keep beside the EVE client, with the timer, the cargo fields (or the
    payout field) and Log button, the session's profit, ISK/hour and runs, and the last three runs. It shares the
    timer and session with the full window; **Unpin** lets other windows cover it and **Expand** brings the full
    window back.
  - **Sign-in:** works out of the box with the app's built-in EVE client ID (public, PKCE, no secret). Set the
    `EVE_CLIENT_ID` environment variable only to override it with your own registered application.
  - **Run detection:** when signed in, switch on **Detect runs from EVE** in the session toolbar. The app polls your
    character's location (ESI caches it for 5 seconds), starts the timer when you enter Abyssal Deadspace, and on
    exit pauses it and prompts you to log the run.
  - **Incursion payouts:** when signed in, switch on **Log payouts from EVE** on the Incursion page. Each incursion
    payout in your wallet journal (a *Corporate Reward Payout*) is logged as a site with the amount actually paid,
    timed from the previous site, or from the session start for the first. ESI caches the journal for an hour, so
    sites can appear up to an hour after you run them; keep the session open until they do. A payout is only
    logged once, so a site you delete stays deleted.
  - **Wallet stat:** when signed in, the Abyss page shows your wallet balance read from ESI ("from EVE at HH:MM"),
    refreshed when a session starts or resumes and after each logged run. It is read-only; signed out it shows "—".
  - Every run is saved immediately, so closing the app mid-session picks up where you left off.
  - Amounts are in millions of ISK; you can type `1,250`, `1.25b` or `800k`. Times accept `14.5` or `14:30`.

**Terminal tracker (`main.py`):** the original menu-driven tracker, now saving to the same database and showing ISK/hour.

Data is stored in SQLite at `%APPDATA%\AbyssTracker\tracker.db` on Windows
(`~/.local/share/AbyssTracker/tracker.db` elsewhere). Set `ABYSS_TRACKER_DB` to use a different file.

## What it reads from your character

Signing in is optional; the app tracks runs you type in without it. If you sign in, it asks CCP's SSO for five read-only ESI scopes:

| Scope | Used for |
|---|---|
| `esi-location.read_location.v1` | Seeing when you enter and leave Abyssal Deadspace, to start and stop the timer |
| `esi-location.read_ship_type.v1` | Knowing which ship is your active ship |
| `esi-location.read_online.v1` | Pausing detection when you are logged out |
| `esi-wallet.read_character_wallet.v1` | The read-only wallet figure, and incursion payouts from the wallet journal |
| `esi-assets.read_assets.v1` | The "Fetch from EVE" button, which values your active ship's cargo |

All scopes are read-only; the app cannot move ISK or items. Your refresh token is kept in the OS keychain (Windows Credential Manager, macOS Keychain). The app talks only to CCP's servers (`login.eveonline.com` and `esi.evetech.net`), and the sign-in callback listens on `127.0.0.1` only. Your runs live in a local SQLite file and are never uploaded. Sign out in the app, or revoke the token from your EVE account page, at any time. The source is here to read.

## How profit works

A run's profit is the **cargo value after minus the cargo value before**, both taken from your active ship's cargo hold. You can type them (EVE's inventory shows an estimated value) or press **Fetch from EVE**. Cargo is priced at CCP's **average market price**, not Jita sell, so the figure is stable and not what you'd get from a particular buy order. Filaments and ammo used up leave the hold, so they come out of the profit on their own.

The wallet takes no part in abyssal runs, because most runners hold loot and sell it later. Items with no market price (abyssal modules, for example) are counted but not valued. Add them by hand. The reasoning is in [ADR 0001](docs/adr/0001-run-profit-from-cargo-not-wallet.md). Incursion sites are the exception: they log the actual payout from your wallet journal.

## Known limits

- Builds exist for Windows and Apple Silicon Macs only. Linux can run from source.
- Builds are unsigned: expect a SmartScreen or Gatekeeper warning (steps below).
- ESI caches the wallet journal for an hour, so incursion payouts can show up to an hour after the site.
- ESI caches assets for up to an hour, so fetched cargo can be stale right after a run. You can edit the numbers.
- Items inside containers in your hold are not counted.
- Items without a market price are not valued.

## Screenshots

Screenshots use sample data.

**Incursion page**: payout per site, site stopwatch and live session stats.

![Incursion page with a live session and the site stopwatch](docs/screenshots/incursion.png)

**History page**: lifetime totals, profit per session (hover a bar for details) and every past session.

![History page with lifetime totals, the profit-per-session chart and the session list](docs/screenshots/history.png)

## Getting Started

### Download

Ready-to-run builds are attached to each [release](https://github.com/Fazorath/AbyssTracker/releases); no Python needed.

- **Windows:** download `AbyssTracker-windows.exe` and run it. SmartScreen may warn because the file isn't signed:
  choose *More info → Run anyway*.
- **macOS (Apple Silicon):** download `AbyssTracker-macos.zip`, unzip it and move `AbyssTracker.app` to Applications.
  The app isn't notarized, so the first time right-click it and choose *Open*.

To run from source instead:

### Prerequisites

Python 3.10+ with Tkinter (included in the installers from [python.org](https://www.python.org/)).

### Installation

1. Clone the repository to your local machine:
   ```bash
   git clone https://github.com/Fazorath/AbyssTracker.git
   cd AbyssTracker
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Desktop app:
```bash
cd EveProfitManager
python gui.py
```
Shortcuts: `Enter` logs a run/site, `Ctrl+1/2/3` switches between Abyss, Incursion and History.

Terminal version:
```bash
cd EveProfitManager
python main.py
```

Build the standalone app yourself (a `.exe` on Windows, an `.app` on macOS, in `dist/`):
```bash
pip install pyinstaller
cd EveProfitManager
pyinstaller AbyssTracker.spec
```
Pushing a `v*` tag (e.g. `git tag v1.0.0 && git push origin v1.0.0`) builds both on GitHub Actions and attaches
them to a release. The app icon is drawn by `make_icon.py`; files in `assets/` are bundled into the build.

Run the tests:
```bash
cd EveProfitManager
python -m unittest discover
```

## Contributing
Contributions are welcome! If you find any bugs or have suggestions for improvements, please open an issue or submit a pull request.

## License

MIT, see [LICENSE](LICENSE). The bundled UI font, Chakra Petch, is under the SIL Open Font License; see `EveProfitManager/assets/fonts/OFL.txt`.

Development history is in [CHANGELOG.md](CHANGELOG.md).

---

EVE Online, the EVE logo, EVE and all associated logos and designs are the intellectual property of CCP hf. All artwork, screenshots, characters, vehicles, storylines, world facts or other recognizable features of the intellectual property relating to these trademarks are likewise the intellectual property of CCP hf. EVE Online and the EVE logo are the registered trademarks of CCP hf. All rights reserved. This project is not affiliated with or endorsed by CCP hf.
