---
name: run-windows
description: Launch, check and screenshot AbyssTracker on the Windows PC with a live EVE character logged in. Use when asked to test the app in its real setting (ESI token, location, run detection, wallet, every page, pocket mode on top of the EVE client).
---

# Run AbyssTracker on the Windows PC

## Hard rules (read first, never negotiable)

- **Computer use may control only:** AbyssTracker, a terminal, and a browser. The browser may open only `login.eveonline.com`, `127.0.0.1:8765/callback`, and Gmail (see below).
- **Never send input to the EVE launcher or client:** no clicks, no keystrokes, no window automation. CCP's EULA bans automating client input. If EVE has focus, stop; don't click. Reading EVE's window (`GetWindowRect`, `IsIconic`, its style flags) is fine; never call `SetWindowPos`, `SetForegroundWindow`, `ShowWindow` or send messages to an EVE window handle.
- **Never type the EVE account password. Never handle authenticator-app codes.** If the sign-in asks for either, stop and hand over to the user.
- **You may approve the ESI SSO sign-in yourself:** pick the character and click Authorize.
- **Emailed verification codes:** you may open Gmail and read **only the newest CCP/EVE email** with the code. Read nothing else; archive, delete and mark nothing. **The moment you open Gmail, send the user a push notification, and start your final report with a bold line saying you opened Gmail, when, and why.**
- **No undocking, no filaments, no Abyssal activation, ever.** The character stays docked for the whole test.
- **Never open the real `tracker.db`.** Every run sets `ABYSS_TRACKER_DB` to a throwaway file.
- **Live screenshots stay on the PC, outside the repo** (they show character name, wallet, location; the repo is public). The PR lists pass/fail per check. Any image put in a PR has the name, portrait, wallet and location blurred first.

## How you reach the desktop

Use the Claude desktop app's computer use on the PC. SSH is not part of the rig: an SSH session shows no GUI and can't read the ESI token from Windows Credential Manager. The PC's OpenSSH server is off at the moment, so don't plan on SSH even for headless jobs; run tests from the terminal on the desktop.

## Before a run (the user does this)

Log in through the EVE launcher, dock the character, and set EVE to windowed or fixed-window mode so the pocket window can sit on top. If EVE isn't docked and windowed, stop and ask.

## Launch

Needs `EVE_CLIENT_ID` (the app's client ID from developers.eveonline.com; callback `http://127.0.0.1:8765/callback`) set in the user's environment. If it's missing, stop and ask; don't hunt for it in files.

```powershell
git clone https://github.com/Fazorath/AbyssTracker.git $env:TEMP\abyss-rig   # or git pull in an existing clone
cd $env:TEMP\abyss-rig
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd EveProfitManager
..\.venv\Scripts\python -m unittest discover     # headless sanity check first
$env:ABYSS_TRACKER_DB = "$env:TEMP\abyss-rig-throwaway.db"
..\.venv\Scripts\python gui.py
```

Delete the throwaway db afterwards. The release `.exe` is out of scope.

## Checks (screenshot each; save under `%USERPROFILE%\Pictures\abyss-rig\<date>\`, never in the repo)

1. **Start:** the app opens from the fresh clone with no errors in the terminal.
2. **Token:** Settings → sign in. The browser opens `login.eveonline.com`; pick the character and Authorize (see rules for passwords, codes and email). Close and reopen the app: it must be signed in with no browser step (refresh works from the stored token).
3. **Location and detection:** with the character docked, switch on **Detect runs from EVE** on the Abyss page. Leave it polling at least a minute. It must not start the timer or prompt to log a run (no false Abyss entry). Report only that the character reads as not in the Abyss; don't write the system or station name into the report or PR.
4. **Wallet:** the Abyss page's Wallet stat shows "from EVE at HH:MM". Ask the user to read the wallet in the client (you may not touch EVE) and compare; they must match.
5. **Pages:** open and screenshot Abyss, Incursion, History and pocket mode.
6. **Pocket on top:** enter pocket mode and check it by window geometry, not a screenshot (EVE is masked in computer-use screenshots). Read the EVE client and pocket windows' rects and the pocket's `WS_EX_TOPMOST` flag, move the pocket over the client with `SetWindowPos` on the pocket's own handle, and confirm the pocket is above the client in z-order. Pass if it is; fail if it's covered or loses topmost. After **Unpin**, the topmost flag must clear. See the notes below for the calls.

Active-ship and cargo checks are not part of this skill (see #52).

## Report

Lead with the Gmail line if you opened Gmail. Then list pass/fail for each check above, with a short note for any fail. Don't paste screenshots with personal details.

## Notes from the first run

- `request_access` only matches installed apps: ask for "Python 3.11" to drive the Tk window (not "python" or "AbyssTracker"). Don't grant the EVE client; its windows are masked in screenshots, which is what you want.
- The refresh token may already be in Windows Credential Manager from an earlier sign-in. If Settings shows the character signed in, don't sign in again: restarting the app and fetching the wallet proves the refresh, and Gmail stays closed.
- The location check can run headless with the app's own code (`Account().client()` plus `location.get_location`); print only `in_abyss`, never the system or token.
- Pocket-on-top is checked without touching EVE: read the EVE client (`exefile`) and pocket windows with Win32 `GetWindowRect`, `IsIconic` and the `WS_EX_TOPMOST` flag, and move the pocket window over the client with `SetWindowPos` on the pocket's own handle. An EVE window that reads as minimized (rect -32000) means the user must restore it.
- The wallet check compares against the figure the user reads in the client; ESI caches it about two minutes, so expect rounding or small drift.
