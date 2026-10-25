"""Read where Sansha incursions are active, and their state, from ESI's public incursions endpoint."""
from dataclasses import dataclass

STATES = ("established", "mobilizing", "withdrawing")  # in the order an incursion is worth running


@dataclass(frozen=True)
class Incursion:
    constellation: str
    staging: str  # the system the fleet stages in
    state: str
    systems: int  # infested solar systems
    influence: float  # 0 to 1; how much of the constellation is still Sansha-held
    has_boss: bool


def get_incursions(client):
    """
    The active incursions, established ones first. Needs no sign-in.

    A constellation or system whose name can't be read shows as its ID instead.
    """
    body = client.get("/incursions", auth=False)
    if not isinstance(body, list):
        raise ValueError(f"Unexpected incursions response: {body!r}")
    names = {}  # path -> name, so a repeated constellation or system is read once
    found = []
    for entry in body:
        state = entry.get("state") if isinstance(entry, dict) else None
        constellation, staging = _id(entry, "constellation_id"), _id(entry, "staging_solar_system_id")
        systems = entry.get("infested_solar_systems") if isinstance(entry, dict) else None
        if state not in STATES or constellation is None or staging is None or not isinstance(systems, list):
            raise ValueError(f"Unexpected incursion: {entry!r}")
        found.append(Incursion(
            constellation=_name(client, names, f"/universe/constellations/{constellation}",
                                f"Constellation {constellation}"),
            staging=_name(client, names, f"/universe/systems/{staging}", f"System {staging}"),
            state=state,
            systems=len(systems),
            influence=float(entry.get("influence") or 0),
            has_boss=bool(entry.get("has_boss")),
        ))
    return sorted(found, key=lambda i: STATES.index(i.state))


def _id(entry, key):
    value = entry.get(key) if isinstance(entry, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _name(client, names, path, fallback):
    if path not in names:
        try:
            names[path] = client.get(path, auth=False)["name"]
        except Exception:  # a missing name shouldn't hide the incursion
            names[path] = fallback
    return names[path]
