"""Read the character's wallet balance from ESI, in the app's millions of ISK."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Wallet:
    millions: float
    fetched_at: float  # when ESI last answered; the balance itself is cached for 120 s


def get_wallet(client, character_id):
    path = f"/characters/{character_id}/wallet"
    balance = client.get(path)
    if isinstance(balance, bool) or not isinstance(balance, (int, float)):
        raise ValueError(f"Unexpected wallet response: {balance!r}")
    return Wallet(millions=balance / 1e6, fetched_at=client.fetched_at(path))
