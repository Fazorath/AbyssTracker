import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from core import ABYSS, INCURSION, Tracker, isk_per_hour, parse_sessions_txt

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

    def test_settings(self):
        self.assertEqual(self.tracker.get_setting("x", "d"), "d")
        self.tracker.set_setting("x", 31)
        self.tracker.set_setting("x", 32)
        self.assertEqual(self.tracker.get_setting("x"), "32")


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


if __name__ == "__main__":
    unittest.main()
