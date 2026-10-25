import unittest

from loot import Assets, LootValue, get_assets, get_prices, value_change

ASSETS = "/characters/123/assets"


class FakeClient:
    """Stands in for EsiClient: serves canned bodies and page counts by path."""

    def __init__(self, bodies, pages=None, fetched_at=1_700_000_000.0):
        self.bodies = bodies
        self._pages = pages or {}
        self._fetched_at = fetched_at

    def get(self, path, auth=True):
        return self.bodies[path]

    def pages(self, path):
        return self._pages.get(path, 1)

    def fetched_at(self, path):
        return self._fetched_at


def item(type_id, quantity=1, **extra):
    return {"item_id": type_id * 10, "type_id": type_id, "quantity": quantity,
            "location_id": 60003760, "location_flag": "Hangar", "location_type": "station",
            "is_singleton": False, **extra}


class GetAssetsTests(unittest.TestCase):
    def test_adds_up_each_type_across_every_page_and_skips_blueprint_copies(self):
        client = FakeClient({
            f"{ASSETS}?page=1": [item(47_762, 3), item(34, 1_000), item(1_234, is_blueprint_copy=True)],
            f"{ASSETS}?page=2": [item(47_762, 2, location_flag="Cargo")],
        }, pages={f"{ASSETS}?page=1": 2}, fetched_at=1_700_000_123.0)
        self.assertEqual(get_assets(client, 123),
                         Assets(character_id=123, quantities={47_762: 5, 34: 1_000}, fetched_at=1_700_000_123.0))

    def test_rejects_a_response_that_is_not_a_list_of_items(self):
        for body in ({"error": "x"}, [{"type_id": 34}], [item(34, quantity="5")]):
            with self.subTest(body=body), self.assertRaises(ValueError):
                get_assets(FakeClient({f"{ASSETS}?page=1": body}), 123)


class GetPricesTests(unittest.TestCase):
    def test_uses_the_average_price_or_else_the_adjusted_one(self):
        client = FakeClient({"/markets/prices": [
            {"type_id": 34, "average_price": 4.5, "adjusted_price": 4.1},
            {"type_id": 47_762, "adjusted_price": 1_200_000.0},
            {"type_id": 52_227},  # an abyssal module: never traded on the market
        ]})
        self.assertEqual(get_prices(client), {34: 4.5, 47_762: 1_200_000.0})

    def test_rejects_a_response_that_is_not_a_list_of_prices(self):
        for body in ({"error": "x"}, [{"average_price": 4.5}], [{"type_id": 34, "average_price": "4.5"}]):
            with self.subTest(body=body), self.assertRaises(ValueError):
                get_prices(FakeClient({"/markets/prices": body}))


class ValueChangeTests(unittest.TestCase):
    def test_values_what_was_gained_less_what_was_used_up_in_millions(self):
        before = {34: 10_000, 47_762: 1, 30_000: 500}  # tritanium, a filament, ammo
        after = {34: 10_000, 30_000: 100, 49_000: 2}  # filament used, ammo shot, two drops
        prices = {34: 4.5, 47_762: 1_200_000.0, 30_000: 500.0, 49_000: 2_100_000.0}
        self.assertEqual(value_change(before, after, prices), LootValue(millions=2.8, unpriced=0))

    def test_counts_the_kinds_of_item_with_no_price(self):
        self.assertEqual(value_change({}, {52_227: 1, 52_228: 1, 34: 1_000_000}, {34: 4.5}),
                         LootValue(millions=4.5, unpriced=2))


if __name__ == "__main__":
    unittest.main()
