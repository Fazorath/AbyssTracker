import unittest

from cargo import Cargo, get_cargo
from test_loot import FakeClient, item

SHIP = "/characters/123/ship"
ASSETS = "/characters/123/assets"
SHIP_ID = 1_050_000_000_001


def in_hold(type_id, quantity=1, **extra):
    return item(type_id, quantity, location_id=SHIP_ID, location_flag="Cargo", location_type="item", **extra)


def client(first_page, second_page=None, prices=None, ship=None, fetched_at=1_700_000_000.0):
    bodies = {
        SHIP: {"ship_item_id": SHIP_ID, "ship_name": "x", "ship_type_id": 17_738} if ship is None else ship,
        f"{ASSETS}?page=1": first_page,
        "/markets/prices": [{"type_id": 34, "average_price": 5.0}, {"type_id": 47_762, "adjusted_price": 1_000_000.0}]
        if prices is None else prices,
    }
    pages = {}
    if second_page is not None:
        bodies[f"{ASSETS}?page=2"] = second_page
        pages[f"{ASSETS}?page=1"] = 2
    return FakeClient(bodies, pages=pages, fetched_at=fetched_at)


class GetCargoTests(unittest.TestCase):
    def test_values_the_cargo_in_millions_with_the_time_esi_last_answered(self):
        c = client([in_hold(34, 2_000_000), in_hold(47_762, 3)], fetched_at=1_700_000_123.0)
        self.assertEqual(get_cargo(c, 123), Cargo(millions=13.0, unpriced=0, fetched_at=1_700_000_123.0))

    def test_ammo_in_the_cargo_hold_counts(self):
        c = client([in_hold(47_762, 100)])
        self.assertEqual(get_cargo(c, 123).millions, 100.0)

    def test_only_the_active_ships_cargo_flag_counts(self):
        c = client([
            in_hold(34, 1_000_000),
            item(34, 1_000_000, location_id=SHIP_ID, location_flag="DroneBay", location_type="item"),
            item(34, 1_000_000, location_id=SHIP_ID, location_flag="HiSlot0", location_type="item"),
            item(34, 1_000_000, location_id=SHIP_ID, location_flag="LoSlot0", location_type="item"),
            item(34, 1_000_000, location_id=SHIP_ID + 1, location_flag="Cargo", location_type="item"),  # another ship
            item(34, 1_000_000),  # a station hangar
            item(34, 1_000_000, location_id=9_000_000_000_001, location_flag="Unlocked", location_type="item"),  # a container
        ])
        self.assertEqual(get_cargo(c, 123).millions, 5.0)

    def test_follows_the_asset_pages(self):
        c = client([in_hold(34, 1_000_000)], [in_hold(34, 1_000_000)])
        self.assertEqual(get_cargo(c, 123).millions, 10.0)

    def test_leaves_out_blueprint_copies(self):
        c = client([in_hold(34, 1_000_000), in_hold(47_762, is_blueprint_copy=True)])
        self.assertEqual(get_cargo(c, 123).millions, 5.0)

    def test_counts_unpriced_item_types_and_leaves_them_out_of_the_value(self):
        c = client([in_hold(34, 1_000_000), in_hold(52_227), in_hold(52_227), in_hold(52_228, 4)])
        cargo = get_cargo(c, 123)
        self.assertEqual((cargo.millions, cargo.unpriced), (5.0, 2))

    def test_an_empty_hold_is_worth_nothing(self):
        self.assertEqual(get_cargo(client([item(34)]), 123).millions, 0.0)

    def test_rejects_malformed_bodies(self):
        good = [in_hold(34)]
        cases = {
            "ship not a dict": client(good, ship=[1]),
            "ship without an item id": client(good, ship={"ship_type_id": 1}),
            "ship id not whole": client(good, ship={"ship_item_id": "7"}),
            "assets not a list": client({"error": "x"}),
            "asset without a location": client([{"type_id": 34, "quantity": 1}]),
            "prices not a list": client(good, prices={"error": "x"}),
        }
        for name, c in cases.items():
            with self.subTest(name), self.assertRaises(ValueError):
                get_cargo(c, 123)


if __name__ == "__main__":
    unittest.main()
