import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from core import ABYSS, INCURSION, Baseline, Loot, Totals, Tracker, best_weather, isk_per_hour, parse_sessions_txt
from journal import Payout
from loot import LootValue

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

    def test_abyss_runs_chain_wallets(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000)
        self.tracker.log_abyss_run(sid, self.tracker.current_isk(sid), 1031, time_left=5)
        self.tracker.log_abyss_run(sid, self.tracker.current_isk(sid), 1050, time_left=8)
        session = self.tracker.session(sid)
        self.assertEqual(session.profit, 50)
        self.assertEqual(session.minutes, 27)
        self.assertEqual(session.runs, 2)
        self.assertEqual(self.tracker.current_isk(sid), 1050)

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


class LootTest(unittest.TestCase):
    def setUp(self):
        self.tracker = Tracker(":memory:")
        self.sid = self.tracker.start_session(ABYSS, starting_isk=1000)

    def test_the_first_baseline_of_a_session_is_the_one_kept(self):
        self.assertIsNone(self.tracker.loot_baseline(self.sid))
        self.tracker.set_loot_baseline(self.sid, 123, {34: 1_000, 47_762: 2})
        self.tracker.set_loot_baseline(self.sid, 456, {34: 5})  # e.g. read again after a restart
        self.assertEqual(self.tracker.loot_baseline(self.sid), Baseline(123, {34: 1_000, 47_762: 2}))

    def test_the_latest_valuation_is_kept_with_when_the_assets_were_read(self):
        self.assertIsNone(self.tracker.loot(self.sid))
        self.tracker.set_loot_baseline(self.sid, 123, {})
        as_of = datetime(2026, 10, 25, 18, 40)
        self.tracker.set_loot(self.sid, LootValue(millions=12.5, unpriced=0), datetime(2026, 10, 25, 18, 0))
        self.tracker.set_loot(self.sid, LootValue(millions=48.25, unpriced=2), as_of)
        self.assertEqual(self.tracker.loot(self.sid), Loot(millions=48.25, unpriced=2, as_of=as_of))

    def test_an_abandoned_session_takes_its_loot_with_it(self):
        self.tracker.set_loot_baseline(self.sid, 123, {34: 1_000})
        self.tracker.end_session(self.sid)  # no runs, so the session is deleted
        self.assertIsNone(self.tracker.loot_baseline(self.sid))


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
