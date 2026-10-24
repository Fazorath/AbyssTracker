import unittest

from clock import read_clock

TWENTY_MINUTES = 20 * 60


class CountdownTest(unittest.TestCase):
    def test_a_fresh_countdown_shows_the_full_time_ready_to_start(self):
        face = read_clock(TWENTY_MINUTES, 0, running=False)
        self.assertEqual(face.text, "20:00")
        self.assertEqual(face.state, "ready")
        self.assertEqual(face.urgency, "normal")
        self.assertEqual(face.share_left, 1.0)

    def test_a_running_countdown_rounds_partial_seconds_up(self):
        face = read_clock(TWENTY_MINUTES, 734.2, running=True)  # 7:45.8 left
        self.assertEqual(face.text, "07:46")
        self.assertEqual(face.state, "running")
        self.assertAlmostEqual(face.share_left, 465.8 / 1200)

    def test_warns_under_five_minutes_and_turns_critical_under_two(self):
        self.assertEqual(read_clock(TWENTY_MINUTES, 900, running=True).urgency, "normal")  # 5:00 left
        self.assertEqual(read_clock(TWENTY_MINUTES, 901, running=True).urgency, "warning")  # 4:59
        self.assertEqual(read_clock(TWENTY_MINUTES, 1080, running=True).urgency, "warning")  # 2:00
        self.assertEqual(read_clock(TWENTY_MINUTES, 1081, running=False).urgency, "critical")  # paused at 1:59

    def test_a_stopped_countdown_with_time_on_it_is_paused(self):
        self.assertEqual(read_clock(TWENTY_MINUTES, 60, running=False).state, "paused")

    def test_a_countdown_past_zero_is_expired_and_stays_at_zero(self):
        face = read_clock(TWENTY_MINUTES, 1300, running=True)
        self.assertEqual(face.text, "00:00")
        self.assertEqual(face.state, "expired")
        self.assertEqual(face.urgency, "critical")
        self.assertEqual(face.share_left, 0.0)


class StopwatchTest(unittest.TestCase):
    def test_counts_up_whole_seconds_without_a_share_or_warnings(self):
        face = read_clock(None, 1385.9, running=True)  # 23:05.9 in
        self.assertEqual(face.text, "23:05")
        self.assertEqual(face.state, "running")
        self.assertEqual(face.urgency, "normal")
        self.assertIsNone(face.share_left)

    def test_starts_ready_at_zero_and_pauses(self):
        self.assertEqual(read_clock(None, 0, running=False).text, "00:00")
        self.assertEqual(read_clock(None, 0, running=False).state, "ready")
        self.assertEqual(read_clock(None, 90, running=False).state, "paused")


if __name__ == "__main__":
    unittest.main()
