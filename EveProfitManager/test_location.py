import unittest

from location import AbyssWatcher, get_location


class FakeClient:
    """Stands in for EsiClient: serves canned bodies by path."""

    def __init__(self, bodies):
        self.bodies = bodies

    def get(self, path):
        return self.bodies[path]


class GetLocationTests(unittest.TestCase):
    def test_a_system_in_the_abyssal_range_is_abyssal_space(self):
        client = FakeClient({"/characters/123/location": {"solar_system_id": 32000456}})
        location = get_location(client, 123)
        self.assertEqual(location.system_id, 32000456)
        self.assertTrue(location.in_abyss)

    def test_a_known_space_system_is_not_abyssal_space(self):
        client = FakeClient({"/characters/123/location": {"solar_system_id": 30000142}})  # Jita
        self.assertFalse(get_location(client, 123).in_abyss)

    def test_rejects_a_response_without_a_solar_system(self):
        client = FakeClient({"/characters/123/location": {"error": "x"}})
        with self.assertRaises(ValueError):
            get_location(client, 123)


class AbyssWatcherTests(unittest.TestCase):
    def test_reports_entering_and_leaving_the_abyss(self):
        watcher = AbyssWatcher()
        self.assertIsNone(watcher.see(False))
        self.assertEqual(watcher.see(True), "entered")
        self.assertIsNone(watcher.see(True))
        self.assertEqual(watcher.see(False), "left")
        self.assertIsNone(watcher.see(False))

    def test_the_first_reading_is_a_baseline_even_inside_the_abyss(self):
        watcher = AbyssWatcher()
        self.assertIsNone(watcher.see(True))  # the run began before we looked: no event
        self.assertEqual(watcher.see(False), "left")


if __name__ == "__main__":
    unittest.main()
