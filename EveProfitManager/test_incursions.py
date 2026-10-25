import unittest

from incursions import Incursion, get_incursions


class FakeClient:
    """Stands in for EsiClient: serves canned bodies by path and records the auth flag."""

    def __init__(self, bodies):
        self.bodies = bodies
        self.auth_used = []

    def get(self, path, auth=True):
        self.auth_used.append(auth)
        if path not in self.bodies:
            raise RuntimeError("not found")
        return self.bodies[path]


def raw(**over):
    body = {
        "constellation_id": 20000100, "faction_id": 500019, "has_boss": True,
        "infested_solar_systems": [30000001, 30000002, 30000003], "influence": 0.5,
        "staging_solar_system_id": 30000001, "state": "established", "type": "Incursion",
    }
    body.update(over)
    return body


NAMES = {
    "/universe/constellations/20000100": {"name": "Tanoo"},
    "/universe/systems/30000001": {"name": "Jita"},
}


class GetIncursionsTests(unittest.TestCase):
    def test_returns_named_incursions_without_signing_in(self):
        client = FakeClient({"/incursions": [raw()], **NAMES})
        self.assertEqual(
            get_incursions(client),
            [Incursion(constellation="Tanoo", staging="Jita", state="established", systems=3,
                       influence=0.5, has_boss=True)],
        )
        self.assertEqual(set(client.auth_used), {False})

    def test_falls_back_to_ids_when_a_name_cannot_be_read(self):
        client = FakeClient({"/incursions": [raw()]})
        incursion = get_incursions(client)[0]
        self.assertEqual(incursion.constellation, "Constellation 20000100")
        self.assertEqual(incursion.staging, "System 30000001")

    def test_orders_established_before_mobilizing_before_withdrawing(self):
        client = FakeClient({"/incursions": [
            raw(state="withdrawing"), raw(state="established"), raw(state="mobilizing"),
        ], **NAMES})
        self.assertEqual([i.state for i in get_incursions(client)],
                         ["established", "mobilizing", "withdrawing"])

    def test_no_active_incursions_is_an_empty_list(self):
        self.assertEqual(get_incursions(FakeClient({"/incursions": []})), [])

    def test_rejects_an_unexpected_response(self):
        with self.assertRaises(ValueError):
            get_incursions(FakeClient({"/incursions": {"error": "x"}}))
        with self.assertRaises(ValueError):
            get_incursions(FakeClient({"/incursions": [raw(state="weird")]}))


if __name__ == "__main__":
    unittest.main()
