"""
Shared tracking logic and storage for the CLI and the desktop UI.

All ISK amounts are in millions, all times are in minutes.
"""
import csv
import hashlib
import math
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
WEATHERS = ("Electrical", "Dark", "Exotic", "Firestorm", "Gamma")
# Filament tier words, indexed by tier: "Fierce Firestorm Filament" is a T3 Firestorm
TIERS = ("Tranquil", "Calm", "Agitated", "Fierce", "Raging", "Chaotic", "Cataclysmic")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    starting_isk REAL,
    imported INTEGER NOT NULL DEFAULT 0,
    import_key TEXT,
    weather TEXT,
    tier INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    recorded_at TEXT NOT NULL,
    profit REAL NOT NULL,
    minutes REAL NOT NULL,
    isk_after REAL,
    count INTEGER NOT NULL DEFAULT 1,
    cargo_before REAL,
    cargo_after REAL
);
CREATE TABLE IF NOT EXISTS payouts (
    journal_id INTEGER PRIMARY KEY
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


def tier_label(tier):
    """Format a filament tier as 'T3 Fierce'."""
    return f"T{tier} {TIERS[tier]}"


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
    isk_after: float | None  # wallet after an old wallet-based run
    count: int
    cargo_before: float | None = None  # set, with cargo_after, on a cargo run
    cargo_after: float | None = None


@dataclass
class Session:
    id: int
    kind: str
    started_at: datetime
    ended_at: datetime | None
    starting_isk: float | None
    imported: bool
    weather: str | None = None
    tier: int | None = None
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
    wins: int  # sessions that ended in profit

    @property
    def isk_per_hour(self):
        return isk_per_hour(self.profit, self.minutes)


def best_weather(by_weather):
    """
    The weather with the highest ISK/hour.

    Args:
        by_weather (dict): Totals keyed by weather, as from Tracker.totals_by_weather().

    Returns:
        str | None: The weather, or None if no known weather has runs.
    """
    known = [w for w in by_weather if w is not None]
    return max(known, key=lambda w: by_weather[w].isk_per_hour, default=None)


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
        self._migrate()

    def _migrate(self):
        self.db.executescript(SCHEMA)
        columns = [r["name"] for r in self.db.execute("PRAGMA table_info(sessions)")]
        # Columns added after the first release, for databases created before them
        for column, type_ in (("import_key", "TEXT"), ("weather", "TEXT"), ("tier", "INTEGER")):
            if column not in columns:
                self.db.execute(f"ALTER TABLE sessions ADD COLUMN {column} {type_}")
        columns = [r["name"] for r in self.db.execute("PRAGMA table_info(runs)")]
        for column in ("cargo_before", "cargo_after"):  # added, never back-filled (ADR 0001)
            if column not in columns:
                self.db.execute(f"ALTER TABLE runs ADD COLUMN {column} REAL")

    def close(self):
        self.db.close()

    # --- sessions -------------------------------------------------------

    def start_session(self, kind, starting_isk=None, weather=None, tier=None):
        """
        Open a new session.

        Args:
            kind (str): ABYSS or INCURSION.
            starting_isk (float, optional): Wallet before the first run, kept for old
                wallet-based sessions. New abyss sessions start without one.
            weather (str, optional): Abyssal weather from WEATHERS.
            tier (int, optional): Filament tier, 0 (Tranquil) to 6 (Cataclysmic).

        Returns:
            int: The new session id.
        """
        _require_filament(kind, weather, tier)
        with self.db:
            cur = self.db.execute(
                "INSERT INTO sessions (kind, started_at, starting_isk, weather, tier) VALUES (?, ?, ?, ?, ?)",
                (kind, _now(), starting_isk, weather, tier),
            )
        if weather is not None:
            self.set_setting("abyss_weather", weather)
            self.set_setting("abyss_tier", tier)
        return cur.lastrowid

    def last_filament(self):
        """
        The weather and tier of the last abyss session started with a filament.

        Returns:
            tuple: (weather, tier), or (None, None) if none has been picked yet.
        """
        weather, tier = self.get_setting("abyss_weather"), self.get_setting("abyss_tier")
        try:
            _require_filament(ABYSS, weather, int(tier))
        except (TypeError, ValueError):
            return None, None
        return weather, int(tier)

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

    def log_cargo_run(self, session_id, cargo_before, cargo_after, time_left):
        """
        Record an abyssal run from the cargo value before and after it, and the timer.

        Profit is cargo after minus cargo before, so it can be negative (lost cargo).

        Args:
            session_id (int): Session to add the run to.
            cargo_before (float): Cargo value going in.
            cargo_after (float): Cargo value coming out.
            time_left (float): Minutes left on the abyssal timer when leaving.

        Returns:
            Run: The recorded run.
        """
        _require_finite(cargo_before, cargo_after)
        _require_time_left(time_left)
        with self.db:
            cur = self.db.execute(
                "INSERT INTO runs (session_id, recorded_at, profit, minutes, cargo_before, cargo_after) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, _now(), cargo_after - cargo_before, MAXTIME - time_left, cargo_before, cargo_after),
            )
        return self.run(cur.lastrowid)

    def latest_cargo_after(self, session_id):
        """
        Cargo after of the session's latest cargo run, to prefill the next run's cargo before.

        Returns:
            float | None: None for a session with no cargo runs (new, or wallet runs only).
        """
        row = self.db.execute(
            "SELECT cargo_after FROM runs WHERE session_id = ? AND cargo_after IS NOT NULL "
            "ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return row["cargo_after"] if row else None

    def log_incursion_site(self, session_id, profit, minutes):
        """Record one incursion site."""
        _require_finite(profit)
        _require_minutes(minutes)
        return self._add_run(session_id, profit, minutes, None)

    def log_incursion_payouts(self, session_id, payouts):
        """
        Record each incursion payout from the wallet journal as a site.

        A site's time runs from the session start, or the latest site logged
        before it was paid, to its payout. Payouts already seen are skipped, so a
        site deleted afterwards stays deleted.

        Args:
            session_id (int): Session to add the sites to.
            payouts (list[journal.Payout]): Payouts in any order.

        Returns:
            list[Run]: The sites recorded, oldest first.
        """
        started_at = self.session(session_id).started_at
        logged = []
        for payout in sorted(payouts, key=lambda p: (p.paid_at, p.journal_id)):
            seen = self.db.execute("SELECT 1 FROM payouts WHERE journal_id = ?", (payout.journal_id,)).fetchone()
            if seen or payout.paid_at < started_at:
                continue
            paid_at = payout.paid_at.isoformat(timespec="seconds")
            row = self.db.execute(
                "SELECT MAX(recorded_at) AS last FROM runs WHERE session_id = ? AND recorded_at <= ?",
                (session_id, paid_at),
            ).fetchone()
            since = datetime.fromisoformat(row["last"]) if row["last"] else started_at
            with self.db:  # the site and its payout are saved together, or neither is
                self.db.execute("INSERT INTO payouts (journal_id) VALUES (?)", (payout.journal_id,))
                run_id = self._insert_run(
                    session_id, payout.millions, (payout.paid_at - since).total_seconds() / 60, None, 1, paid_at
                )
            logged.append(self.run(run_id))
        return logged

    def _add_run(self, session_id, profit, minutes, isk_after, count=1, recorded_at=None):
        with self.db:
            run_id = self._insert_run(session_id, profit, minutes, isk_after, count, recorded_at)
        return self.run(run_id)

    def _insert_run(self, session_id, profit, minutes, isk_after, count, recorded_at):
        """Insert a run inside the caller's transaction; returns its id."""
        cur = self.db.execute(
            "INSERT INTO runs (session_id, recorded_at, profit, minutes, isk_after, count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, recorded_at or _now(), profit, minutes, isk_after, count),
        )
        return cur.lastrowid

    def run(self, run_id):
        row = self.db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _run(row) if row else None

    def runs(self, session_id):
        rows = self.db.execute(
            "SELECT * FROM runs WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
        return [_run(r) for r in rows]

    def delete_run(self, run_id):
        """Delete a run. Every other run keeps its profit."""
        with self.db:
            self.db.execute("DELETE FROM runs WHERE id = ?", (run_id,))

    def edit_wallet_run(self, run_id, profit, minutes):
        """
        Correct an old wallet run's profit or time. Its wallet stays as it was
        and no other run changes.

        Args:
            run_id (int): Old wallet run (wallet after set, no cargo values) to change.
            profit (float): Corrected profit in millions.
            minutes (float): Corrected run time.

        Returns:
            Run: The updated run.
        """
        _require_finite(profit)
        _require_minutes(minutes)
        run = self.run(run_id)
        if run is None or run.isk_after is None or run.cargo_after is not None:
            raise ValueError("Only old wallet runs have a profit to correct this way")
        with self.db:
            self.db.execute("UPDATE runs SET profit = ?, minutes = ? WHERE id = ?", (profit, minutes, run_id))
        return self.run(run_id)

    def edit_cargo_run(self, run_id, cargo_before, cargo_after, time_left):
        """
        Correct a cargo run's cargo values or timer. Its profit stands on its own
        cargo values, so no other run changes.

        Args:
            run_id (int): Cargo run to change.
            cargo_before (float): Corrected cargo value going in.
            cargo_after (float): Corrected cargo value coming out.
            time_left (float): Corrected minutes left on the abyssal timer.

        Returns:
            Run: The updated run.
        """
        _require_finite(cargo_before, cargo_after)
        _require_time_left(time_left)
        run = self.run(run_id)
        if run is None or run.cargo_after is None:
            raise ValueError("Only cargo runs have cargo values to correct")
        with self.db:
            self.db.execute(
                "UPDATE runs SET profit = ?, minutes = ?, cargo_before = ?, cargo_after = ? WHERE id = ?",
                (cargo_after - cargo_before, MAXTIME - time_left, cargo_before, cargo_after, run_id),
            )
        return self.run(run_id)

    def edit_incursion_site(self, run_id, profit, minutes):
        """Correct an incursion site's payout or time."""
        _require_finite(profit)
        _require_minutes(minutes)
        run = self.run(run_id)
        if run is None or self.session(run.session_id).kind != INCURSION:
            raise ValueError("Only incursion sites have a payout to correct")
        with self.db:
            self.db.execute("UPDATE runs SET profit = ?, minutes = ? WHERE id = ?", (profit, minutes, run_id))
        return self.run(run_id)

    # --- stats ----------------------------------------------------------

    def totals(self, kind=None):
        """Lifetime totals, optionally for one kind."""
        where, args = ("WHERE s.kind = ?", (kind,)) if kind else ("", ())
        row = self.db.execute(_totals_query(where), args).fetchone()
        return _totals(row)

    def totals_by_weather(self):
        """
        Lifetime abyss totals for each weather that has runs.

        Returns:
            dict: Totals keyed by weather in WEATHERS order, with sessions that
            have no weather recorded under None at the end.
        """
        rows = self.db.execute(
            _totals_query("WHERE s.kind = ?", "weather"), (ABYSS,)
        ).fetchall()
        found = {r["weather"]: _totals(r) for r in rows}
        return {w: found[w] for w in (*WEATHERS, None) if w in found}

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
        Each entry is keyed by its text and how many identical entries came
        before it, so re-importing a file that has grown only adds the new ones.

        Args:
            path (str | Path): Path to Sessions.txt.

        Returns:
            int: Number of sessions imported.
        """
        imported = 0
        with self.db:  # one transaction: all entries or none
            for entry in parse_sessions_txt(Path(path).read_text(encoding="utf-8", errors="replace")):
                if self.db.execute(
                    "SELECT 1 FROM sessions WHERE import_key = ?", (entry["key"],)
                ).fetchone():
                    continue
                stamp = (entry["date"] or datetime(1970, 1, 1)).isoformat(timespec="seconds")
                cur = self.db.execute(
                    "INSERT INTO sessions (kind, started_at, ended_at, imported, import_key) "
                    "VALUES (?, ?, ?, 1, ?)",
                    (entry["kind"], stamp, stamp, entry["key"]),
                )
                self.db.execute(
                    "INSERT INTO runs (session_id, recorded_at, profit, minutes, isk_after, count) "
                    "VALUES (?, ?, ?, ?, NULL, ?)",
                    (cur.lastrowid, stamp, entry["profit"], entry["minutes"], entry["runs"]),
                )
                imported += 1
        return imported

    # --- export and backup ----------------------------------------------

    def export_csv(self, path, kind=None):
        """
        Write every run with its session to a CSV file, oldest session first.

        A session with no runs yet gets one row with the run columns empty.

        Args:
            path (str | Path): File to write, replacing any existing one.
            kind (str, optional): Only export ABYSS or INCURSION sessions.

        Returns:
            int: Number of rows written.
        """
        where, args = ("WHERE s.kind = ?", (kind,)) if kind else ("", ())
        rows = self.db.execute(
            "SELECT s.id AS session_id, s.kind, s.started_at, s.ended_at, s.weather, s.tier, s.imported, "
            "r.id AS run_id, r.recorded_at, r.profit AS profit_millions, r.minutes, "
            "r.isk_after AS isk_after_millions, r.count AS runs, "
            "r.cargo_before AS cargo_before_millions, r.cargo_after AS cargo_after_millions "
            f"FROM sessions s LEFT JOIN runs r ON r.session_id = s.id {where} ORDER BY s.started_at, s.id, r.id",
            args,
        ).fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            out = csv.writer(f)
            out.writerow(_CSV_COLUMNS)
            out.writerows(tuple("" if row[c] is None else row[c] for c in _CSV_COLUMNS) for row in rows)
        return len(rows)

    def backup(self, path):
        """
        Save a consistent copy of the whole database, replacing any file at path.

        Args:
            path (str | Path): Where to put the copy.

        Raises:
            ValueError: If path is the live database itself.
        """
        live = self.db.execute("PRAGMA database_list").fetchone()["file"]
        if live and os.path.exists(path) and os.path.samefile(live, path):
            raise ValueError("Choose a different file than the live database")
        target = sqlite3.connect(path)
        try:
            self.db.backup(target)
        except sqlite3.Error:
            target.close()
            Path(path).unlink(missing_ok=True)  # don't leave half a backup that looks like a real one
            raise
        finally:
            target.close()

    def restore(self, path):
        """
        Replace all data with the contents of a backup made by backup().

        The file is checked first, so a bad file leaves the current data alone.
        Backups from older versions are brought up to the current schema.

        Args:
            path (str | Path): Backup file.

        Raises:
            ValueError: If path isn't an intact tracker database.
        """
        try:
            source = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
        except sqlite3.Error as err:
            raise ValueError(f"Can't open {path}: {err}") from err
        try:
            try:
                if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("The backup file is damaged")
                tables = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            except sqlite3.DatabaseError:
                tables = set()
            if not {"sessions", "runs"} <= tables:
                raise ValueError("That isn't an AbyssTracker database")
            source.backup(self.db)
        finally:
            source.close()
        self._migrate()
        self.db.commit()


def parse_sessions_txt(text):
    """
    Parse the old Sessions.txt summaries.

    Args:
        text (str): File contents.

    Returns:
        list[dict]: Entries with kind, profit, runs, minutes, date (datetime or None)
        and a stable import key.
    """
    entries = []
    seen = {}
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
        digest = hashlib.sha1(" ".join(block.split()).encode()).hexdigest()
        seen[digest] = seen.get(digest, 0) + 1
        key = f"{digest}#{seen[digest]}"
        entries.append(dict(kind=kind, profit=profit, runs=runs, minutes=minutes, date=date, key=key))
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


def _require_finite(*values):
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError("Amounts and times must be real numbers")


def _require_minutes(minutes):
    _require_finite(minutes)
    if minutes < 0:
        raise ValueError("Time can't be negative")


def _require_time_left(time_left):
    _require_finite(time_left)
    if not 0 <= time_left <= MAXTIME:
        raise ValueError(f"Time left must be between 0 and {MAXTIME:g} minutes")


def _require_filament(kind, weather, tier):
    if weather is None and tier is None:
        return
    if kind != ABYSS:
        raise ValueError("Only abyss sessions have a filament")
    if weather not in WEATHERS:
        raise ValueError(f"Weather must be one of {', '.join(WEATHERS)}")
    if isinstance(tier, bool) or not (isinstance(tier, int) and 0 <= tier < len(TIERS)):
        raise ValueError(f"Tier must be 0 to {len(TIERS) - 1}")


def _now():
    return datetime.now().isoformat(timespec="seconds")


_CSV_COLUMNS = (
    "session_id", "kind", "started_at", "ended_at", "weather", "tier", "imported",
    "run_id", "recorded_at", "profit_millions", "minutes", "isk_after_millions", "runs",
    "cargo_before_millions", "cargo_after_millions",  # last, so older columns keep their place
)

_SESSION_QUERY = (
    "SELECT s.*, COALESCE(SUM(r.profit), 0) AS profit, COALESCE(SUM(r.minutes), 0) AS minutes, "
    "COALESCE(SUM(r.count), 0) AS run_count FROM sessions s LEFT JOIN runs r ON r.session_id = s.id"
)


def _totals_query(where, group=None):
    """
    SQL for totals over per-session sums, so a session with a positive total counts as a win.

    Args:
        where (str): WHERE clause on the sessions table (alias s), or "".
        group (str, optional): sessions column to total by; it is selected too.

    Returns:
        str: SQL selecting profit, minutes, runs, sessions and wins.
    """
    select, group_by = (f"{group}, ", f" GROUP BY {group}") if group else ("", "")
    return (
        f"SELECT {select}COALESCE(SUM(profit), 0) AS profit, COALESCE(SUM(minutes), 0) AS minutes, "
        "COALESCE(SUM(runs), 0) AS runs, COUNT(*) AS sessions, COALESCE(SUM(profit > 0), 0) AS wins FROM ("
        "SELECT s.id, s.weather, SUM(r.profit) AS profit, SUM(r.minutes) AS minutes, SUM(r.count) AS runs "
        f"FROM sessions s JOIN runs r ON r.session_id = s.id {where} GROUP BY s.id){group_by}"
    )


def _session(row):
    return Session(
        id=row["id"],
        kind=row["kind"],
        started_at=datetime.fromisoformat(row["started_at"]),
        ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        starting_isk=row["starting_isk"],
        imported=bool(row["imported"]),
        weather=row["weather"],
        tier=row["tier"],
        profit=row["profit"],
        minutes=row["minutes"],
        runs=row["run_count"],
    )


def _totals(row):
    return Totals(row["profit"], row["minutes"], row["runs"], row["sessions"], row["wins"])


def _run(row):
    return Run(
        id=row["id"],
        session_id=row["session_id"],
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
        profit=row["profit"],
        minutes=row["minutes"],
        isk_after=row["isk_after"],
        count=row["count"],
        cargo_before=row["cargo_before"],
        cargo_after=row["cargo_after"],
    )
