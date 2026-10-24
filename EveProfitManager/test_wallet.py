import unittest

from wallet import Wallet, get_wallet


class FakeClient:
    """Stands in for EsiClient: serves canned bodies by path."""

    def __init__(self, bodies, fetched_at=1_700_000_000.0):
        self.bodies = bodies
        self._fetched_at = fetched_at

    def get(self, path):
        return self.bodies[path]

    def fetched_at(self, path):
        return self._fetched_at


class GetWalletTests(unittest.TestCase):
    def test_balance_is_returned_in_millions_with_the_time_esi_last_answered(self):
        client = FakeClient({"/characters/123/wallet": 1_250_500_000.0}, fetched_at=1_700_000_123.0)
        self.assertEqual(get_wallet(client, 123), Wallet(millions=1250.5, fetched_at=1_700_000_123.0))

    def test_rejects_a_non_numeric_balance(self):
        client = FakeClient({"/characters/123/wallet": {"error": "x"}})
        with self.assertRaises(ValueError):
            get_wallet(client, 123)


if __name__ == "__main__":
    unittest.main()
