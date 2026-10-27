import csv
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core import ABYSS, INCURSION, Tracker


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.tracker = Tracker(":memory:")
        self.addCleanup(self.tracker.close)

    def rows(self, path):
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def seed(self):
        a = self.tracker.start_session(ABYSS, starting_isk=1000, weather="Dark", tier=3)
        self.tracker.log_abyss_run(a, 1000, 1031, time_left=5)
        self.tracker.log_abyss_run(a, 1031, 1050, time_left=8)
        self.tracker.end_session(a)
        i = self.tracker.start_session(INCURSION)
        self.tracker.log_incursion_site(i, 93, 12)
        self.tracker.end_session(i)
        return a, i

    def test_csv_has_one_row_per_run_with_its_session(self):
        a, i = self.seed()
        out = self.dir / "out.csv"
        self.assertEqual(self.tracker.export_csv(out), 3)
        rows = self.rows(out)
        self.assertEqual(len(rows), 3)
        first = rows[0]
        self.assertEqual(first["session_id"], str(a))
        self.assertEqual(first["kind"], ABYSS)
        self.assertEqual(first["weather"], "Dark")
        self.assertEqual(first["tier"], "3")
        self.assertEqual(float(first["profit_millions"]), 31.0)
        self.assertEqual(float(first["minutes"]), 15.0)
        self.assertEqual(float(first["isk_after_millions"]), 1031.0)
        self.assertEqual(rows[2]["kind"], INCURSION)
        self.assertEqual(rows[2]["weather"], "")
        self.assertEqual(rows[2]["isk_after_millions"], "")

    def test_csv_can_be_limited_to_one_kind(self):
        self.seed()
        out = self.dir / "out.csv"
        self.assertEqual(self.tracker.export_csv(out, kind=INCURSION), 1)
        self.assertEqual({r["kind"] for r in self.rows(out)}, {INCURSION})

    def test_csv_of_an_empty_tracker_is_just_the_header(self):
        out = self.dir / "out.csv"
        self.assertEqual(self.tracker.export_csv(out), 0)
        self.assertEqual(self.rows(out), [])
        self.assertIn("session_id", out.read_text(encoding="utf-8"))

    def test_csv_keeps_a_session_that_has_no_runs_yet(self):
        sid = self.tracker.start_session(INCURSION)
        out = self.dir / "out.csv"
        self.tracker.export_csv(out)
        (row,) = self.rows(out)
        self.assertEqual(row["session_id"], str(sid))
        self.assertEqual(row["run_id"], "")


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.tracker = Tracker(self.dir / "tracker.db")
        self.addCleanup(self.tracker.close)

    def log(self, profit):
        sid = self.tracker.start_session(INCURSION)
        self.tracker.log_incursion_site(sid, profit, 10)
        self.tracker.end_session(sid)

    def test_backup_is_a_copy_that_opens_as_a_tracker(self):
        self.log(50)
        copy = self.dir / "backup.db"
        self.tracker.backup(copy)
        other = Tracker(copy)
        self.assertEqual(other.totals().profit, 50)
        other.close()

    def test_backup_replaces_an_older_backup_file(self):
        copy = self.dir / "backup.db"
        self.log(50)
        self.tracker.backup(copy)
        self.log(25)
        self.tracker.backup(copy)
        other = Tracker(copy)
        self.assertEqual(other.totals().profit, 75)
        other.close()

    def test_backup_onto_the_live_database_is_refused(self):
        with self.assertRaises(ValueError):
            self.tracker.backup(self.dir / "tracker.db")
        self.assertEqual(self.tracker.totals().sessions, 0)

    def test_restore_replaces_the_data_and_keeps_the_tracker_usable(self):
        self.log(50)
        copy = self.dir / "backup.db"
        self.tracker.backup(copy)
        self.log(25)
        self.tracker.set_setting("abyss_weather", "Dark")
        self.tracker.restore(copy)
        self.assertEqual(self.tracker.totals().profit, 50)
        self.assertEqual(self.tracker.totals().sessions, 1)
        self.assertIsNone(self.tracker.get_setting("abyss_weather"))
        self.log(5)  # still writable afterwards
        self.assertEqual(self.tracker.totals().profit, 55)

    def test_restore_from_a_database_older_than_the_current_schema(self):
        old = self.dir / "old.db"
        db = sqlite3.connect(old)
        db.executescript(
            "CREATE TABLE sessions (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, started_at TEXT NOT NULL,"
            " ended_at TEXT, starting_isk REAL, imported INTEGER NOT NULL DEFAULT 0);"
            "CREATE TABLE runs (id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, recorded_at TEXT NOT NULL,"
            " profit REAL NOT NULL, minutes REAL NOT NULL, isk_after REAL, count INTEGER NOT NULL DEFAULT 1);"
            "INSERT INTO sessions (kind, started_at, ended_at) VALUES ('abyss', '2024-06-17T23:54:00', '2024-06-17T23:54:00');"
            "INSERT INTO runs (session_id, recorded_at, profit, minutes) VALUES (1, '2024-06-17T23:54:00', 10, 19);"
        )
        db.commit()
        db.close()
        self.tracker.restore(old)
        self.assertEqual(self.tracker.totals().profit, 10)
        self.assertIsNone(self.tracker.session(1).weather)
        self.assertIsNone(self.tracker.runs(1)[0].cargo_after)
        self.tracker.log_cargo_run(1, 0, 5, time_left=10)
        self.tracker.start_session(ABYSS, starting_isk=1, weather="Dark", tier=1)

    def test_restore_refuses_files_that_are_not_trackers(self):
        self.log(50)
        junk = self.dir / "junk.db"
        junk.write_text("not a database at all" * 50)
        other = self.dir / "other.db"
        db = sqlite3.connect(other)
        db.execute("CREATE TABLE unrelated (x)")
        db.commit()
        db.close()
        for bad in (junk, other, self.dir / "missing.db"):
            with self.assertRaises(ValueError):
                self.tracker.restore(bad)
        self.assertEqual(self.tracker.totals().profit, 50)
        self.assertFalse((self.dir / "missing.db").exists())


if __name__ == "__main__":
    unittest.main()
