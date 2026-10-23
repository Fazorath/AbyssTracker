"""
Shared tracking logic and storage for the CLI and the desktop UI.

All ISK amounts are in millions, all times are in minutes.
"""
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MAXTIME = 20.00  # Length of the abyssal timer in minutes
ABYSS = "abyss"
INCURSION = "incursion"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    starting_isk REAL,
    imported INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    recorded_at TEXT NOT NULL,
    profit REAL NOT NULL,
    minutes REAL NOT NULL,
    isk_after REAL,
    count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def default_db_path():
    """
    Where the database lives: $ABYSS_TRACKER_DB, else the per-user app data folder.

    Returns:
        Path: Path to the SQLite database file.
    """
    if os.environ.get("ABYSS_TRACKER_DB"):
        return Path(os.environ["ABYSS_TRACKER_DB"])
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "AbyssTracker" / "tracker.db"


def isk_per_hour(profit, minutes):
    """
    Average profit per hour.

    Args:
        profit (float): Profit in millions.
        minutes (float): Time spent in minutes.

    Returns:
        float: Millions per hour, 0 if no time was spent.
    """
    return profit / (minutes / 60) if minutes > 0 else 0.0


def format_minutes(minutes):
    """Format minutes as '1h 05m' or '19m'."""
    minutes = int(round(minutes))
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins:02d}m" if hours else f"{mins}m"


def format_isk(millions):
    """Format millions of ISK as '31.0M' or '1.25B'."""
    if abs(millions) >= 1000:
        return f"{millions / 1000:,.2f}B"
    return f"{millions:,.1f}M"


@dataclass
class Run:
    id: int
    session_id: int
    recorded_at: datetime
    profit: float
    minutes: float
    isk_after: float | None
    count: int


@dataclass
class Session:
    id: int
    kind: str
    started_at: datetime
    ended_at: datetime | None
    starting_isk: float | None
    imported: bool
    profit: float = 0.0
    minutes: float = 0.0
    runs: int = 0

    @property
    def isk_per_hour(self):
        return isk_per_hour(self.profit, self.minutes)

    @property
    def active(self):
        return self.ended_at is None


@dataclass
class Totals:
    profit: float
    minutes: float
    runs: int
    sessions: int

    @property
    def isk_per_hour(self):
        return isk_per_hour(self.profit, self.minutes)


class Tracker:
    """
    SQLite-backed store for sessions and the runs/sites inside them.
    """

    def __init__(self, path=None):
        path = Path(path) if path else default_db_path()
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    # --- sessions -------------------------------------------------------

    def start_session(self, kind, starting_isk=None):
        """
        Open a new session.

        Args:
            kind (str): ABYSS or INCURSION.
            starting_isk (float, optional): Wallet before the first abyssal run.

        Returns:
            int: The new session id.
        """
        with self.db:
            cur = self.db.execute(
                "INSERT INTO sessions (kind, started_at, starting_isk) VALUES (?, ?, ?)",
                (kind, _now(), starting_isk),
            )
        return cur.lastrowid

    def end_session(self, session_id):
        """Close a session. Sessions with no runs are deleted instead."""
        with self.db:
            if not self.runs(session_id):
                self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            else:
                self.db.execute(
                    "UPDATE sessions SET ended_at = ? WHERE id = ?", (_now(), session_id)
                )

    def active_session(self, kind):
        """Return the open session of this kind, if the app was closed mid-session."""
        row = self.db.execute(
            "SELECT id FROM sessions WHERE kind = ? AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
            (kind,),
        ).fetchone()
        return self.session(row["id"]) if row else None

    def session(self, session_id):
        row = self.db.execute(_SESSION_QUERY + " WHERE s.id = ? GROUP BY s.id", (session_id,)).fetchone()
        return _session(row) if row else None

    def sessions(self, kind=None):
        """All sessions with their totals, newest first."""
        where, args = ("WHERE s.kind = ?", (kind,)) if kind else ("", ())
        rows = self.db.execute(
            _SESSION_QUERY + f" {where} GROUP BY s.id ORDER BY s.started_at DESC, s.id DESC", args
        ).fetchall()
        return [_session(r) for r in rows]

    def delete_session(self, session_id):
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    # --- runs -----------------------------------------------------------

    def log_abyss_run(self, session_id, isk_before, isk_after, time_left):
        """
        Record an abyssal run from wallet amounts and the timer.

        Args:
            session_id (int): Session to add the run to.
            isk_before (float): Wallet before the run.
            isk_after (float): Wallet after the run.
            time_left (float): Minutes left on the abyssal timer when leaving.

        Returns:
            Run: The recorded run.
        """
        if not 0 <= time_left <= MAXTIME:
            raise ValueError(f"Time left must be between 0 and {MAXTIME:g} minutes")
        return self._add_run(session_id, isk_after - isk_before, MAXTIME - time_left, isk_after)

    def log_incursion_site(self, session_id, profit, minutes):
        """Record one incursion site."""
        if minutes < 0:
            raise ValueError("Time can't be negative")
        return self._add_run(session_id, profit, minutes, None)

    def _add_run(self, session_id, profit, minutes, isk_after, count=1, recorded_at=None):
        with self.db:
            cur = self.db.execute(
                "INSERT INTO runs (session_id, recorded_at, profit, minutes, isk_after, count) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, recorded_at or _now(), profit, minutes, isk_after, count),
            )
        return self.run(cur.lastrowid)

    def run(self, run_id):
        row = self.db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _run(row) if row else None

    def runs(self, session_id):
        rows = self.db.execute(
            "SELECT * FROM runs WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
        return [_run(r) for r in rows]

    def delete_run(self, run_id):
        with self.db:
            self.db.execute("DELETE FROM runs WHERE id = ?", (run_id,))

    def current_isk(self, session_id):
        """Wallet after the latest abyssal run, or the starting wallet if none yet."""
        row = self.db.execute(
            "SELECT isk_after FROM runs WHERE session_id = ? AND isk_after IS NOT NULL "
            "ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if row:
            return row["isk_after"]
        session = self.session(session_id)
        return session.starting_isk if session else None

    # --- stats ----------------------------------------------------------

    def totals(self, kind=None):
        """Lifetime totals, optionally for one kind."""
        where, args = ("WHERE s.kind = ?", (kind,)) if kind else ("", ())
        row = self.db.execute(
            "SELECT COALESCE(SUM(r.profit), 0) AS profit, COALESCE(SUM(r.minutes), 0) AS minutes, "
            "COALESCE(SUM(r.count), 0) AS runs, COUNT(DISTINCT s.id) AS sessions "
            f"FROM sessions s JOIN runs r ON r.session_id = s.id {where}",
            args,
        ).fetchone()
        return Totals(row["profit"], row["minutes"], row["runs"], row["sessions"])

    # --- settings -------------------------------------------------------

    def get_setting(self, key, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        with self.db:
            self.db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    # --- import ---------------------------------------------------------

    def import_sessions_txt(self, path):
        """
        Import session summaries from the old Sessions.txt format.

        Each summary becomes a closed session holding a single row with the
        session totals, since the old file didn't keep per-run details.
        Summaries already imported (same kind, date and totals) are skipped.

        Args:
            path (str | Path): Path to Sessions.txt.

        Returns:
            int: Number of sessions imported.
        """
        imported = 0
        for entry in parse_sessions_txt(Path(path).read_text(encoding="utf-8", errors="replace")):
            when = entry["date"] or datetime(1970, 1, 1)
            stamp = when.isoformat(timespec="seconds")
            duplicate = self.db.execute(
                "SELECT 1 FROM sessions s JOIN runs r ON r.session_id = s.id "
                "WHERE s.imported = 1 AND s.kind = ? AND s.started_at = ? "
                "AND r.profit = ? AND r.minutes = ? AND r.count = ?",
                (entry["kind"], stamp, entry["profit"], entry["minutes"], entry["runs"]),
            ).fetchone()
            if duplicate:
                continue
            with self.db:
                cur = self.db.execute(
                    "INSERT INTO sessions (kind, started_at, ended_at, imported) VALUES (?, ?, ?, 1)",
                    (entry["kind"], stamp, stamp),
                )
            self._add_run(
                cur.lastrowid, entry["profit"], entry["minutes"], None, entry["runs"], stamp
            )
            imported += 1
        return imported


def parse_sessions_txt(text):
    """
    Parse the old Sessions.txt summaries.

    Args:
        text (str): File contents.

    Returns:
        list[dict]: Entries with kind, profit, runs, minutes and date (datetime or None).
    """
    entries = []
    for block in text.split("-------------------"):
        if "Abyss Details" in block:
            kind = ABYSS
        elif "Incursion Details" in block:
            kind = INCURSION
        else:
            continue
        profit = _match(r"Total Profit:\s*(-?[\d.]+)", block, float, 0.0)
        runs = _match(r"Total (?:Abyssal runs|Incursions Ran):\s*(\d+)", block, int, 0)
        minutes = _match(r"Total Time:\s*([\d.]+)", block, float, 0.0)
        date = _match(r"Date:\s*(.+)", block, _parse_date, None)
        entries.append(dict(kind=kind, profit=profit, runs=runs, minutes=minutes, date=date))
    return entries


def _parse_date(text):
    text = text.strip()
    try:
        return datetime.strptime(text, "%m-%d-%Y %I:%M %p")
    except ValueError:
        pass
    # Early entries were written with a broken format like "06-06/17/24-2024 11:53:PM"
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2}).*?(\d{1,2}):(\d{2}):?\s*([AP]M)", text)
    if match:
        month, day, year, hour, minute, ampm = match.groups()
        return datetime.strptime(f"{month}/{day}/{year} {hour}:{minute} {ampm}", "%m/%d/%y %I:%M %p")
    return None


def _match(pattern, text, convert, default):
    match = re.search(pattern, text)
    if not match:
        return default
    try:
        return convert(match.group(1))
    except ValueError:
        return default


def _now():
    return datetime.now().isoformat(timespec="seconds")


_SESSION_QUERY = (
    "SELECT s.*, COALESCE(SUM(r.profit), 0) AS profit, COALESCE(SUM(r.minutes), 0) AS minutes, "
    "COALESCE(SUM(r.count), 0) AS run_count FROM sessions s LEFT JOIN runs r ON r.session_id = s.id"
)


def _session(row):
    return Session(
        id=row["id"],
        kind=row["kind"],
        started_at=datetime.fromisoformat(row["started_at"]),
        ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        starting_isk=row["starting_isk"],
        imported=bool(row["imported"]),
        profit=row["profit"],
        minutes=row["minutes"],
        runs=row["run_count"],
    )


def _run(row):
    return Run(
        id=row["id"],
        session_id=row["session_id"],
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
        profit=row["profit"],
        minutes=row["minutes"],
        isk_after=row["isk_after"],
        count=row["count"],
    )
