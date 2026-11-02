# AbyssTracker

Desktop app that logs EVE Online abyssal runs and incursion sites with their ISK profit (millions of ISK, minutes). Vocabulary: `CONTEXT.md` (Run, Session, Cargo before/after, Run profit). Public repo.

## Stack and commands
- Python 3.10 to 3.13, CustomTkinter GUI, ESI/SSO via `requests`, `PyJWT`, `keyring`. Code lives in `EveProfitManager/`.
- Install: `pip install -r requirements.txt` (in a venv). Tests: `cd EveProfitManager && python -m unittest discover` (this is what CI runs, on 3.10 and 3.13).
- Run: `cd EveProfitManager && ABYSS_TRACKER_DB=/tmp/abyss-test.db python main.py`. Always set `ABYSS_TRACKER_DB` to a throwaway file; the default is the user's real database.
- Release: tag `v*` builds Windows and macOS binaries with PyInstaller (`AbyssTracker.spec`). A PR touching the spec, `assets/` or `requirements.txt` triggers the build job; keep it green.

## Layout
- `EveProfitManager/gui.py` desktop entry; `main.py` the terminal app; `menu.py`, `settings.py` the shell; `abyss.py`, `incursion.py` the two pages.
- `core.py` the data model and database; `cargo.py`, `loot.py`, `journal.py`, `location.py` read ESI; `esi.py`, `sso.py` sign-in.
- `test_*.py` beside the code they test. `docs/adr/` decisions, `docs/screenshots/` public images.
- `.claude/skills/run-windows/` how a live check on the user's PC works; read it before any "test in the real setting" ticket.

## The user's EVE character (hard rule)
- Never undock, warp, jump, use a filament or start an Abyssal, and never send clicks, keystrokes or window automation to the EVE client (CCP's EULA bans it). Launching the client is fine; the character stays docked.
- A test run happens only inside AbyssTracker with a throwaway `ABYSS_TRACKER_DB`, never against EVE.
- Never type the account password or handle authenticator codes. If sign-in asks for them, stop and put a question card on the ticket.
- Screenshots with character name, wallet or location stay off the repo (it is public); blur before attaching.

## Conventions
- Issues and board: `Fazorath/AbyssTracker`, board "AbyssTracker Roadmap" (#8, Status + Priority + Phase).
- Branch `<n>-<slug>`. Every change to profit maths gets a unit test in `test_core.py` or `test_cargo.py` with the numbers from `CONTEXT.md`'s example dialogue.
- `CHANGELOG.md` gets one line per user-visible change in the same PR.
- GUI changes follow `design-rules` and the existing CustomTkinter theme; no new widget library.
