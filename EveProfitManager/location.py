"""Read the character's location from ESI and notice when they enter or leave Abyssal Deadspace."""
from dataclasses import dataclass

ABYSS_SYSTEMS = range(32_000_000, 33_000_000)  # abyssal pockets have solar system IDs in this block


@dataclass(frozen=True)
class Location:
    system_id: int

    @property
    def in_abyss(self):
        return self.system_id in ABYSS_SYSTEMS


def get_location(client, character_id):
    body = client.get(f"/characters/{character_id}/location")
    system = body.get("solar_system_id") if isinstance(body, dict) else None
    if isinstance(system, bool) or not isinstance(system, int):
        raise ValueError(f"Unexpected location response: {body!r}")
    return Location(system_id=system)


class AbyssWatcher:
    """Turns a stream of in-abyss readings into 'entered' and 'left' events."""

    def __init__(self):
        self._inside = None  # unknown until the first reading

    def see(self, in_abyss):
        """Feed a reading; returns 'entered', 'left', or None when nothing changed.

        The first reading only sets the baseline, so a run already under way when
        watching starts is not reported as an entry.
        """
        before, self._inside = self._inside, in_abyss
        if before is None or before == in_abyss:
            return None
        return "entered" if in_abyss else "left"
