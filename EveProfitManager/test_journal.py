import unittest
from datetime import datetime, timezone

from journal import Payout, get_incursion_payouts

PATH = "/characters/123/wallet/journal"


class FakeClient:
    """Stands in for EsiClient: serves canned bodies by path."""

    def __init__(self, bodies):
        self.bodies = bodies

    def get(self, path):
        return self.bodies[path]


def entry(id_, date, amount, ref_type="corporate_reward_payout"):
    return {"id": id_, "date": date, "ref_type": ref_type, "amount": amount, "description": "x"}


def local(utc_text):
    """The naive local time the app stores for an ESI UTC timestamp."""
    return datetime.fromisoformat(utc_text).replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


class GetIncursionPayoutsTests(unittest.TestCase):
    def test_returns_incursion_payouts_oldest_first_in_millions_and_local_time(self):
        client = FakeClient({PATH: [  # ESI lists the newest entry first
            entry(3, "2026-10-25T18:40:00Z", 31_500_000.0),
            entry(2, "2026-10-25T18:30:00Z", -12_000_000.0, ref_type="market_escrow"),
            entry(1, "2026-10-25T18:28:00Z", 28_750_000.0),
        ]})
        self.assertEqual(get_incursion_payouts(client, 123), [
            Payout(journal_id=1, paid_at=local("2026-10-25T18:28:00"), millions=28.75),
            Payout(journal_id=3, paid_at=local("2026-10-25T18:40:00"), millions=31.5),
        ])

    def test_skips_entries_that_take_isk_away(self):
        client = FakeClient({PATH: [entry(1, "2026-10-25T18:28:00Z", -5_000_000.0)]})
        self.assertEqual(get_incursion_payouts(client, 123), [])

    def test_rejects_a_response_that_is_not_a_list_of_entries(self):
        for body in ({"error": "x"}, [{"id": 1}], [entry("1", "2026-10-25T18:28:00Z", 5.0)]):
            with self.subTest(body=body), self.assertRaises(ValueError):
                get_incursion_payouts(FakeClient({PATH: body}), 123)


if __name__ == "__main__":
    unittest.main()
