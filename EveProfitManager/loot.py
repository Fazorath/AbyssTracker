"""Value the items a session brought back, from the character's assets on ESI and market prices."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Assets:
    quantities: dict  # type_id -> how many the character owns, in every hangar and cargo hold
    fetched_at: float  # when ESI last answered; it caches the asset list for an hour


@dataclass(frozen=True)
class LootValue:
    millions: float  # ISK, at market prices
    unpriced: int  # kinds of item that changed but have no market price, like abyssal modules


def get_assets(client, character_id):
    """
    Everything the character owns, counted by type.

    Blueprint copies are left out: the market price of their type is the
    original's, so they would be valued far above what they are worth.
    """
    path = f"/characters/{character_id}/assets"
    first = f"{path}?page=1"
    items = _items(client.get(first))
    for page in range(2, client.pages(first) + 1):
        items += _items(client.get(f"{path}?page={page}"))
    quantities = {}
    for entry in items:
        if not entry.get("is_blueprint_copy"):
            quantities[entry["type_id"]] = quantities.get(entry["type_id"], 0) + entry["quantity"]
    return Assets(quantities=quantities, fetched_at=client.fetched_at(first))


def get_prices(client):
    """
    ISK per unit for every type the market prices, keyed by type_id.

    This is CCP's average across all regions (or its adjusted price when there
    is no average), so it estimates what loot is worth rather than quoting Jita.
    """
    body = client.get("/markets/prices", auth=False)
    if not isinstance(body, list) or not all(isinstance(e, dict) and _whole(e.get("type_id")) for e in body):
        raise ValueError(f"Unexpected prices response: {body!r}")
    prices = {}
    for entry in body:
        price = entry.get("average_price", entry.get("adjusted_price"))
        if price is None:
            continue
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ValueError(f"Unexpected price: {entry!r}")
        prices[entry["type_id"]] = price
    return prices


def value_change(before, after, prices):
    """
    What the change from the `before` quantities to the `after` ones is worth.

    Items gained count for their value and items used up (filaments, ammo, a
    lost ship) against it, so buying something only moves ISK out of the wallet
    and into the loot.
    """
    isk, unpriced = 0.0, 0
    for type_id in before.keys() | after.keys():
        change = after.get(type_id, 0) - before.get(type_id, 0)
        if not change:
            continue
        if type_id in prices:
            isk += change * prices[type_id]
        else:
            unpriced += 1
    return LootValue(millions=isk / 1e6, unpriced=unpriced)


def _items(body):
    if not isinstance(body, list) or not all(
        isinstance(e, dict) and _whole(e.get("type_id")) and _whole(e.get("quantity")) for e in body
    ):
        raise ValueError(f"Unexpected assets response: {body!r}")
    return body


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)
