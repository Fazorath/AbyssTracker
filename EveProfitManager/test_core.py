import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from core import ABYSS, INCURSION, Totals, Tracker, best_weather, isk_per_hour, parse_sessions_txt
from journal import Payout

OLD_FILE = """Abyss Details!

Total Profit: 10.0 Million
Total Abyssal runs: 1 Runs
Total Time: 19.0 Min
Date: 06-06/17/24-2024 11:53:PM
-------------------
Incursion Details!

Total Profit: 93 Million
Total Incursions Ran: 3 Sites
Total Time: 36 Min
-------------------
Abyss Details!

Total Profit: 10.0 Million
Total Abyssal runs: 1 Runs
Total Time: 19.0 Min
Date: 06-17-2024 11:54 PM
-------------------
"""


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.tracker = Tracker(":memory:")

    def test_cargo_runs_chain_through_the_latest_cargo_after(self):
        sid = self.tracker.start_session(ABYSS)
        self.assertIsNone(self.tracker.latest_cargo_after(sid))
        self.tracker.log_cargo_run(sid, 100, 131, time_left=5)
        self.tracker.log_cargo_run(sid, self.tracker.latest_cargo_after(sid), 150, time_left=8)
        session = self.tracker.session(sid)
        self.assertEqual(session.profit, 50)
        self.assertEqual(session.minutes, 27)
        self.assertEqual(session.runs, 2)
        self.assertEqual(self.tracker.latest_cargo_after(sid), 150)

    def test_a_cargo_run_records_both_values_and_no_wallet(self):
        sid = self.tracker.start_session(ABYSS)
        run = self.tracker.log_cargo_run(sid, 120, 164.5, time_left=6)
        self.assertAlmostEqual(run.profit, 44.5)
        self.assertEqual(run.minutes, 14)
        self.assertEqual((run.cargo_before, run.cargo_after, run.isk_after), (120, 164.5, None))
        self.assertIsNone(self.tracker.session(sid).starting_isk)

    def test_a_cargo_run_can_lose_isk(self):
        sid = self.tracker.start_session(ABYSS)
        run = self.tracker.log_cargo_run(sid, 300, 40, time_left=0)
        self.assertEqual(run.profit, -260)
        self.assertEqual(self.tracker.session(sid).profit, -260)

    def test_bad_cargo_runs_are_rejected_with_the_validator_errors(self):
        sid = self.tracker.start_session(ABYSS)
        inf, nan = float("inf"), float("nan")
        for before, after, left, error in (
            (inf, 100, 5, "real numbers"), (100, nan, 5, "real numbers"), (100, "120", 5, "real numbers"),
            (100, 120, nan, "real numbers"), (100, 120, 25, "between 0 and 20"), (100, 120, -1, "between 0 and 20"),
        ):
            with self.assertRaisesRegex(ValueError, error):
                self.tracker.log_cargo_run(sid, before, after, left)
        self.assertEqual(self.tracker.runs(sid), [])

    def test_latest_cargo_after_skips_wallet_runs_and_other_sessions(self):
        old = self.tracker.start_session(ABYSS, starting_isk=1000)
        self.tracker.log_abyss_run(old, 1000, 1030, time_left=10)
        self.assertIsNone(self.tracker.latest_cargo_after(old))  # wallet runs only
        self.tracker.log_cargo_run(old, 10, 70, time_left=10)
        self.tracker.log_abyss_run(old, 1030, 1040, time_left=10)  # a wallet run after it
        self.assertEqual(self.tracker.latest_cargo_after(old), 70)
        self.assertIsNone(self.tracker.latest_cargo_after(self.tracker.start_session(ABYSS)))

    def test_a_session_open_across_the_update_mixes_wallet_and_cargo_runs(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000, weather="Dark", tier=3)
        self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)  # logged before the update
        self.assertIsNone(self.tracker.latest_cargo_after(sid))  # its first cargo before is empty
        self.tracker.log_cargo_run(sid, 50, 90, time_left=12)
        self.tracker.log_cargo_run(sid, 90, 80, time_left=5)
        self.assertEqual([r.profit for r in self.tracker.runs(sid)], [30, 40, -10])
        session = self.tracker.session(sid)
        self.assertEqual((session.profit, session.minutes, session.runs), (60, 33, 3))
        self.assertAlmostEqual(session.isk_per_hour, 60 / (33 / 60))
        self.assertEqual(self.tracker.totals(ABYSS).profit, 60)
        self.assertEqual(self.tracker.totals_by_weather()["Dark"].profit, 60)
        self.assertEqual(self.tracker.sessions(ABYSS)[0].profit, 60)

    def test_sessions_do_not_leak_profit(self):
        for _ in range(2):
            sid = self.tracker.start_session(ABYSS, starting_isk=100)
            self.tracker.log_abyss_run(sid, 100, 130, time_left=0)
            self.tracker.end_session(sid)
            self.assertEqual(self.tracker.session(sid).profit, 30)
        self.assertEqual(self.tracker.totals().profit, 60)

    def test_time_left_is_validated(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=100)
        with self.assertRaises(ValueError):
            self.tracker.log_abyss_run(sid, 100, 120, time_left=25)

    def test_active_session_and_empty_end(self):
        sid = self.tracker.start_session(INCURSION)
        self.assertEqual(self.tracker.active_session(INCURSION).id, sid)
        self.tracker.end_session(sid)  # no sites: dropped
        self.assertIsNone(self.tracker.session(sid))
        self.assertIsNone(self.tracker.active_session(INCURSION))

    def test_totals_by_kind_and_rate(self):
        sid = self.tracker.start_session(INCURSION)
        self.tracker.log_incursion_site(sid, 31, 10)
        self.tracker.log_incursion_site(sid, 31, 20)
        totals = self.tracker.totals(INCURSION)
        self.assertEqual((totals.profit, totals.minutes, totals.runs), (62, 30, 2))
        self.assertAlmostEqual(totals.isk_per_hour, 124)
        self.assertEqual(self.tracker.totals(ABYSS).runs, 0)
        self.assertEqual(isk_per_hour(10, 0), 0)

    def test_delete_run(self):
        sid = self.tracker.start_session(INCURSION)
        run = self.tracker.log_incursion_site(sid, 31, 10)
        self.tracker.delete_run(run.id)
        self.assertEqual(self.tracker.session(sid).runs, 0)

    def test_deleting_middle_abyss_run_keeps_wallet_gain(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000)
        self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)
        middle = self.tracker.log_abyss_run(sid, 1030, 1060, time_left=10)
        self.tracker.log_abyss_run(sid, 1060, 1100, time_left=10)
        self.tracker.delete_run(middle.id)
        session = self.tracker.session(sid)
        self.assertEqual((session.runs, session.profit), (2, 100))
        self.assertEqual(self.tracker.current_isk(sid), 1100)

    def test_editing_abyss_run_wallet_rebases_next_run(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000)
        self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)
        typo = self.tracker.log_abyss_run(sid, 1030, 1600, time_left=10)  # meant 1060
        last = self.tracker.log_abyss_run(sid, 1600, 1100, time_left=10)
        edited = self.tracker.edit_abyss_run(typo.id, 1060, time_left=4)
        self.assertEqual((edited.profit, edited.minutes, edited.isk_after), (30, 16, 1060))
        self.assertEqual(self.tracker.run(last.id).profit, 40)
        session = self.tracker.session(sid)
        self.assertEqual((session.runs, session.profit, session.minutes), (3, 100, 36))
        self.assertEqual(self.tracker.current_isk(sid), 1100)

    def test_bad_abyss_edits_are_rejected(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000)
        run = self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)
        site = self.tracker.log_incursion_site(self.tracker.start_session(INCURSION), 31, 10)
        for run_id, isk_after, time_left in (
            (run.id, 1030, 25),
            (run.id, 1030, -1),
            (run.id, float("nan"), 5),
            (site.id, 1030, 5),
        ):
            with self.assertRaises(ValueError):
                self.tracker.edit_abyss_run(run_id, isk_after, time_left)
        self.assertEqual(self.tracker.run(run.id), run)
        self.assertEqual(self.tracker.run(site.id), site)

    def test_editing_a_cargo_run_recomputes_its_profit_and_minutes(self):
        sid = self.tracker.start_session(ABYSS)
        typo = self.tracker.log_cargo_run(sid, 100, 1310, time_left=5)  # meant 131
        edited = self.tracker.edit_cargo_run(typo.id, 90, 131, time_left=8)
        self.assertEqual((edited.cargo_before, edited.cargo_after, edited.isk_after), (90, 131, None))
        self.assertEqual((edited.profit, edited.minutes), (41, 12))
        self.assertEqual(self.tracker.session(sid).profit, 41)

    def test_editing_a_cargo_run_leaves_the_runs_around_it_alone(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000)
        wallet = self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)
        first = self.tracker.log_cargo_run(sid, 50, 90, time_left=12)
        middle = self.tracker.log_cargo_run(sid, 90, 900, time_left=6)
        last = self.tracker.log_cargo_run(sid, 900, 120, time_left=5)
        self.tracker.edit_cargo_run(middle.id, 90, 100, time_left=6)
        for run in (wallet, first, last):
            self.assertEqual(self.tracker.run(run.id), run)
        self.assertEqual(self.tracker.latest_cargo_after(sid), 120)

    def test_bad_cargo_edits_are_rejected_like_logging(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000)
        run = self.tracker.log_cargo_run(sid, 100, 131, time_left=5)
        wallet = self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)
        site = self.tracker.log_incursion_site(self.tracker.start_session(INCURSION), 31, 10)
        inf, nan = float("inf"), float("nan")
        for run_id, before, after, left, error in (
            (run.id, inf, 131, 5, "real numbers"), (run.id, 100, nan, 5, "real numbers"),
            (run.id, 100, "131", 5, "real numbers"), (run.id, 100, 131, nan, "real numbers"),
            (run.id, 100, 131, 25, "between 0 and 20"), (run.id, 100, 131, -1, "between 0 and 20"),
            (wallet.id, 1000, 1030, 5, "cargo"), (site.id, 0, 31, 5, "cargo"), (999, 0, 31, 5, "cargo"),
        ):
            with self.assertRaisesRegex(ValueError, error):
                self.tracker.edit_cargo_run(run_id, before, after, left)
        for unchanged in (run, wallet, site):
            self.assertEqual(self.tracker.run(unchanged.id), unchanged)

    def test_editing_incursion_site(self):
        sid = self.tracker.start_session(INCURSION)
        self.tracker.log_incursion_site(sid, 31, 10)
        typo = self.tracker.log_incursion_site(sid, 310, 12)
        edited = self.tracker.edit_incursion_site(typo.id, 31, 14)
        self.assertEqual((edited.profit, edited.minutes), (31, 14))
        session = self.tracker.session(sid)
        self.assertEqual((session.runs, session.profit, session.minutes), (2, 62, 24))

    def test_bad_incursion_edits_are_rejected(self):
        site = self.tracker.log_incursion_site(self.tracker.start_session(INCURSION), 31, 10)
        sid = self.tracker.start_session(ABYSS, starting_isk=1000)
        run = self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)
        for run_id, profit, minutes in ((site.id, 31, -1), (site.id, float("inf"), 10), (run.id, 31, 10)):
            with self.assertRaises(ValueError):
                self.tracker.edit_incursion_site(run_id, profit, minutes)
        self.assertEqual(self.tracker.run(site.id), site)
        self.assertEqual(self.tracker.run(run.id), run)

    def test_non_finite_values_are_rejected(self):
        abyss = self.tracker.start_session(ABYSS, starting_isk=100)
        inc = self.tracker.start_session(INCURSION)
        nan, inf = float("nan"), float("inf")
        for call in (
            lambda: self.tracker.log_abyss_run(abyss, 100, inf, time_left=5),
            lambda: self.tracker.log_abyss_run(abyss, 100, 120, time_left=nan),
            lambda: self.tracker.log_incursion_site(inc, nan, 10),
            lambda: self.tracker.log_incursion_site(inc, 31, inf),
        ):
            with self.assertRaises(ValueError):
                call()
        self.assertEqual(self.tracker.totals().runs, 0)

    def test_abyss_session_keeps_weather_and_tier(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=100, weather="Firestorm", tier=3)
        session = self.tracker.session(sid)
        self.assertEqual((session.weather, session.tier), ("Firestorm", 3))
        inc = self.tracker.session(self.tracker.start_session(INCURSION))
        self.assertEqual((inc.weather, inc.tier), (None, None))

    def test_bad_filament_is_rejected(self):
        for kind, weather, tier in (
            (ABYSS, "Sunny", 3),
            (ABYSS, "Gamma", 7),
            (ABYSS, "Gamma", -1),
            (ABYSS, "Gamma", None),
            (ABYSS, "Gamma", True),
            (ABYSS, None, 2),
            (INCURSION, "Dark", 1),
        ):
            with self.assertRaises(ValueError):
                self.tracker.start_session(kind, weather=weather, tier=tier)
        self.assertEqual(self.tracker.sessions(), [])

    def test_totals_by_weather(self):
        for weather, tier, profit, time_left in (
            ("Gamma", 4, 60, 5),       # 60M in 15 min
            ("Electrical", 3, 20, 10),  # 20M in 10 min
            ("Gamma", 5, 30, 0),       # 30M in 20 min
            (None, None, 10, 10),      # before weather was recorded
        ):
            sid = self.tracker.start_session(ABYSS, starting_isk=100, weather=weather, tier=tier)
            self.tracker.log_abyss_run(sid, 100, 100 + profit, time_left)
        self.tracker.start_session(ABYSS, starting_isk=100, weather="Dark", tier=1)  # no runs yet
        inc = self.tracker.start_session(INCURSION)
        self.tracker.log_incursion_site(inc, 31, 10)

        by_weather = self.tracker.totals_by_weather()
        self.assertEqual(list(by_weather), ["Electrical", "Gamma", None])
        gamma = by_weather["Gamma"]
        self.assertEqual((gamma.profit, gamma.minutes, gamma.runs, gamma.sessions), (90, 35, 2, 2))
        self.assertAlmostEqual(by_weather["Electrical"].isk_per_hour, 120)
        self.assertEqual(by_weather[None].profit, 10)

    def test_winning_sessions_count_session_profit(self):
        for wallets in ((100, 150, 120), (100, 80, 130), (100, 90)):  # +20, +30 with a losing run, -10
            sid = self.tracker.start_session(ABYSS, starting_isk=wallets[0])
            for before, after in zip(wallets, wallets[1:]):
                self.tracker.log_abyss_run(sid, before, after, time_left=5)
        inc = self.tracker.start_session(INCURSION)
        self.tracker.log_incursion_site(inc, 0, 10)  # break-even isn't a win

        self.assertEqual((self.tracker.totals().wins, self.tracker.totals().sessions), (2, 4))
        self.assertEqual(self.tracker.totals(INCURSION).wins, 0)
        self.assertEqual(self.tracker.totals_by_weather()[None].wins, 2)

    def test_best_weather_is_highest_isk_per_hour(self):
        by_weather = {
            "Electrical": Totals(profit=40, minutes=30, runs=2, sessions=1, wins=1),  # 80M/hr
            "Gamma": Totals(profit=90, minutes=60, runs=3, sessions=1, wins=1),       # 90M/hr
            None: Totals(profit=100, minutes=20, runs=1, sessions=1, wins=1),         # unknown weather can't win
        }
        self.assertEqual(best_weather(by_weather), "Gamma")
        self.assertIsNone(best_weather({None: by_weather[None]}))
        self.assertIsNone(best_weather({}))

    def test_settings(self):
        self.assertEqual(self.tracker.get_setting("x", "d"), "d")
        self.tracker.set_setting("x", 31)
        self.tracker.set_setting("x", 32)
        self.assertEqual(self.tracker.get_setting("x"), "32")


class IncursionPayoutTest(unittest.TestCase):
    """Payouts read from the wallet journal become incursion sites."""

    def setUp(self):
        self.tracker = Tracker(":memory:")
        self.sid = self.tracker.start_session(INCURSION)
        self.start = self.tracker.session(self.sid).started_at

    def payout(self, journal_id, minutes_in, millions=31.5):
        return Payout(journal_id=journal_id, paid_at=self.start + timedelta(minutes=minutes_in), millions=millions)

    def test_each_payout_is_a_site_timed_from_the_one_before(self):
        logged = self.tracker.log_incursion_payouts(self.sid, [self.payout(1, 9), self.payout(2, 21, millions=28.75)])
        self.assertEqual([(r.profit, r.minutes, r.recorded_at) for r in logged], [
            (31.5, 9, self.start + timedelta(minutes=9)),
            (28.75, 12, self.start + timedelta(minutes=21)),
        ])
        self.assertEqual(self.tracker.runs(self.sid), logged)

    def test_a_payout_is_logged_once_and_a_deleted_site_stays_deleted(self):
        first = self.tracker.log_incursion_payouts(self.sid, [self.payout(1, 9)])
        self.tracker.delete_run(first[0].id)
        again = self.tracker.log_incursion_payouts(self.sid, [self.payout(1, 9), self.payout(2, 20)])
        self.assertEqual([(r.minutes, r.profit) for r in again], [(20, 31.5)])  # 1 is gone, so 2 times from the start
        self.assertEqual(self.tracker.log_incursion_payouts(self.sid, [self.payout(1, 9), self.payout(2, 20)]), [])
        self.assertEqual(self.tracker.session(self.sid).runs, 1)

    def test_payouts_from_before_the_session_are_not_its_sites(self):
        self.assertEqual(self.tracker.log_incursion_payouts(self.sid, [self.payout(1, -3)]), [])
        self.assertEqual(self.tracker.session(self.sid).runs, 0)

    def test_a_site_logged_by_hand_starts_the_next_payouts_time(self):
        self.tracker.log_incursion_site(self.sid, 31, 10)  # recorded now, just after the session started
        manual = self.tracker.runs(self.sid)[0].recorded_at
        logged = self.tracker.log_incursion_payouts(self.sid, [self.payout(1, 30)])
        self.assertAlmostEqual(logged[0].minutes, (self.start + timedelta(minutes=30) - manual).total_seconds() / 60)


class LootTableTest(unittest.TestCase):
    def tables(self, db):
        return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    def test_a_new_database_has_no_loot_table(self):
        tracker = Tracker(":memory:")
        self.assertNotIn("loot", self.tables(tracker.db))

    def test_an_old_database_with_a_loot_table_still_opens_and_keeps_it(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "old.db")
            tracker = Tracker(path)
            sid = tracker.start_session(ABYSS, starting_isk=1000)
            tracker.db.execute(
                "CREATE TABLE loot (session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE, "
                "character_id INTEGER NOT NULL, baseline TEXT NOT NULL, millions REAL, unpriced INTEGER, as_of TEXT)"
            )
            tracker.db.execute("INSERT INTO loot (session_id, character_id, baseline) VALUES (?, 1, '{}')", (sid,))
            tracker.db.commit()
            tracker.close()
            reopened = Tracker(path)
            self.assertIn("loot", self.tables(reopened.db))
            self.assertEqual(reopened.session(sid).starting_isk, 1000)
            reopened.log_abyss_run(sid, 1000, 1050, 10)
            self.assertEqual(len(reopened.runs(sid)), 1)
            reopened.close()


class ImportTest(unittest.TestCase):
    def test_parse(self):
        entries = parse_sessions_txt(OLD_FILE)
        self.assertEqual([e["kind"] for e in entries], [ABYSS, INCURSION, ABYSS])
        self.assertEqual(entries[0]["date"], datetime(2024, 6, 17, 23, 53))
        self.assertEqual(entries[2]["date"], datetime(2024, 6, 17, 23, 54))
        self.assertIsNone(entries[1]["date"])
        self.assertEqual((entries[1]["profit"], entries[1]["runs"], entries[1]["minutes"]), (93, 3, 36))

    def test_import_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "Sessions.txt"
            path.write_text(OLD_FILE, encoding="utf-8")
            tracker = Tracker(Path(tmp) / "t.db")
            self.assertEqual(tracker.import_sessions_txt(path), 3)
            self.assertEqual(tracker.import_sessions_txt(path), 0)
            totals = tracker.totals()
            self.assertEqual((totals.profit, totals.runs, totals.sessions), (113, 5, 3))
            tracker.close()


    def test_identical_undated_sessions_are_all_imported(self):
        block = (
            "Incursion Details!\n \nTotal Profit: 93 Million\n"
            "Total Incursions Ran: 3 Sites\nTotal Time: 36 Min\n-------------------\n"
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "Sessions.txt"
            path.write_text(block * 2, encoding="utf-8")
            tracker = Tracker(Path(tmp) / "t.db")
            self.assertEqual(tracker.import_sessions_txt(path), 2)
            path.write_text(block * 3, encoding="utf-8")
            self.assertEqual(tracker.import_sessions_txt(path), 1)
            self.assertEqual(tracker.totals(INCURSION).sessions, 3)
            tracker.close()


    def test_database_from_before_import_keys_still_opens(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE sessions (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, started_at TEXT NOT NULL, "
                "ended_at TEXT, starting_isk REAL, imported INTEGER NOT NULL DEFAULT 0)"
            )
            conn.commit()
            conn.close()
            path = Path(tmp) / "Sessions.txt"
            path.write_text(OLD_FILE, encoding="utf-8")
            tracker = Tracker(db)
            self.assertEqual(tracker.import_sessions_txt(path), 3)
            tracker.close()

    def test_database_from_before_filaments_gains_weather_and_tier(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE sessions (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, started_at TEXT NOT NULL, "
                "ended_at TEXT, starting_isk REAL, imported INTEGER NOT NULL DEFAULT 0, import_key TEXT)"
            )
            conn.execute("INSERT INTO sessions (kind, started_at) VALUES ('abyss', '2026-01-01T10:00:00')")
            conn.commit()
            conn.close()
            tracker = Tracker(db)
            old = tracker.sessions()[0]
            self.assertEqual((old.weather, old.tier), (None, None))
            sid = tracker.start_session(ABYSS, starting_isk=100, weather="Dark", tier=4)
            self.assertEqual(tracker.session(sid).weather, "Dark")
            tracker.close()

    def test_database_from_before_cargo_runs_gains_the_cargo_columns_and_keeps_old_runs(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                "CREATE TABLE sessions (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, started_at TEXT NOT NULL, "
                "ended_at TEXT, starting_isk REAL, imported INTEGER NOT NULL DEFAULT 0, import_key TEXT, "
                "weather TEXT, tier INTEGER);"
                "CREATE TABLE runs (id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, recorded_at TEXT NOT NULL, "
                "profit REAL NOT NULL, minutes REAL NOT NULL, isk_after REAL, count INTEGER NOT NULL DEFAULT 1);"
                "INSERT INTO sessions (kind, started_at, starting_isk, weather, tier) "
                "VALUES ('abyss', '2026-10-20T10:00:00', 1000, 'Dark', 3);"
                "INSERT INTO runs (session_id, recorded_at, profit, minutes, isk_after) "
                "VALUES (1, '2026-10-20T10:20:00', 30, 10, 1030);"
            )
            conn.commit()
            conn.close()
            tracker = Tracker(db)
            old = tracker.runs(1)[0]
            self.assertEqual((old.profit, old.minutes, old.isk_after), (30, 10, 1030))
            self.assertEqual((old.cargo_before, old.cargo_after), (None, None))
            self.assertEqual(tracker.totals(ABYSS).profit, 30)
            self.assertIsNone(tracker.latest_cargo_after(1))
            tracker.log_cargo_run(1, 0, 25, time_left=8)  # the session left open carries on
            self.assertEqual(tracker.session(1).profit, 55)
            tracker.close()
            tracker = Tracker(db)  # and opens again once migrated
            self.assertEqual(tracker.latest_cargo_after(1), 25)
            tracker.close()

    def test_last_filament_is_remembered(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            tracker = Tracker(db)
            self.assertEqual(tracker.last_filament(), (None, None))
            tracker.start_session(ABYSS, starting_isk=100, weather="Exotic", tier=2)
            tracker.start_session(ABYSS, starting_isk=100, weather="Gamma", tier=5)
            tracker.start_session(ABYSS, starting_isk=100)  # no filament: keeps the last one
            tracker.close()
            tracker = Tracker(db)
            self.assertEqual(tracker.last_filament(), ("Gamma", 5))
            tracker.close()


if __name__ == "__main__":
    unittest.main()
