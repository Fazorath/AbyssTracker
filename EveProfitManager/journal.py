"""Read incursion payouts from the character's wallet journal on ESI."""
from dataclasses import dataclass
from datetime import datetime

PAYOUT_REF_TYPE = "corporate_reward_payout"  # how CONCORD's incursion site payouts show in the journal


@dataclass(frozen=True)
class Payout:
    journal_id: int
    at: datetime  # local time, like the times the tracker stores
    millions: float


def get_incursion_payouts(client, character_id):
    """
    The incursion payouts in the newest page of the journal, oldest first.

    ESI caches the journal for an hour, so a payout can show up that long after
    the site; its `at` is still when it was paid.
    """
    body = client.get(f"/characters/{character_id}/wallet/journal")
    if not isinstance(body, list) or not all(isinstance(e, dict) and "ref_type" in e for e in body):
        raise ValueError(f"Unexpected journal response: {body!r}")
    payouts = [_payout(e) for e in body if e["ref_type"] == PAYOUT_REF_TYPE]
    return sorted((p for p in payouts if p.millions > 0), key=lambda p: (p.at, p.journal_id))


def _payout(entry):
    journal_id, amount = entry.get("id"), entry.get("amount")
    try:
        at = datetime.fromisoformat(entry["date"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        raise ValueError(f"Unexpected journal entry: {entry!r}") from None
    if isinstance(journal_id, bool) or not isinstance(journal_id, int) or at.tzinfo is None \
            or isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError(f"Unexpected journal entry: {entry!r}")
    return Payout(journal_id=journal_id, at=at.astimezone().replace(tzinfo=None), millions=amount / 1e6)
