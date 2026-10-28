"""Read what the active ship's cargo hold is worth from ESI, in the app's millions of ISK."""
from dataclasses import dataclass

from loot import _items, _whole, get_prices


@dataclass(frozen=True)
class Cargo:
    millions: float
    unpriced: int  # item types with no market price, left out of `millions`
    fetched_at: float  # when ESI last answered for the asset list; it caches it for an hour


def get_cargo(client, character_id):
    """
    The cargo value of the ship EVE says the character is flying now.

    Counts only items directly in that ship with flag Cargo (ammo included), not
    its drone bay, fitted modules, other ships, hangars or containers. Blueprint
    copies are left out, as in the asset reader, because their type's price is
    the original's.
    """
    ship = client.get(f"/characters/{character_id}/ship")
    if not isinstance(ship, dict) or not _whole(ship.get("ship_item_id")):
        raise ValueError(f"Unexpected ship response: {ship!r}")
    path = f"/characters/{character_id}/assets"
    first = f"{path}?page=1"
    items = _items(client.get(first))
    for page in range(2, client.pages(first) + 1):
        items += _items(client.get(f"{path}?page={page}"))
    quantities = {}
    for entry in items:
        if not _whole(entry.get("location_id")) or not isinstance(entry.get("location_flag"), str):
            raise ValueError(f"Unexpected asset: {entry!r}")
        if entry["location_id"] == ship["ship_item_id"] and entry["location_flag"] == "Cargo" \
                and not entry.get("is_blueprint_copy"):
            quantities[entry["type_id"]] = quantities.get(entry["type_id"], 0) + entry["quantity"]
    prices = get_prices(client)
    isk = sum(count * prices[type_id] for type_id, count in quantities.items() if type_id in prices)
    unpriced = sum(1 for type_id in quantities if type_id not in prices)
    return Cargo(millions=isk / 1e6, unpriced=unpriced, fetched_at=client.fetched_at(first))
