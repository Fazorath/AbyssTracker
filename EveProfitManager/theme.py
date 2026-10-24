"""
Filament theme: colour tokens per abyssal weather, used by the desktop UI.
"""
import os
from dataclasses import dataclass

from core import ABYSS, INCURSION

# Icon and other files the UI loads; PyInstaller bundles this folder next to the code
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def asset_path(name):
    """Absolute path of a file in the assets folder."""
    return os.path.join(ASSETS, name)


@dataclass(frozen=True)
class Theme:
    bg: str  # window background
    panel: str  # tiles, tabs and form panels
    line: str  # borders and the ring decoration
    accent: str  # countdown, selected tab and primary buttons
    soft: str  # secondary text
    hint: str = ""  # tactical hint shown under the countdown


WEATHER_THEMES = {
    "Electrical": Theme("#0a0f26", "#141c3d", "#33427a", "#93acff", "#b3bde0",
                        "Watch your cap: electrical drains it"),
    "Dark": Theme("#0b0b0e", "#18181d", "#3a3a44", "#d7d2e6", "#a9a6b6",
                  "Short sight range: approach and orbit close"),
    "Exotic": Theme("#170a22", "#251238", "#523170", "#dc9bff", "#c7b2d6",
                    "Scan resolution down: lock early"),
    "Firestorm": Theme("#1d0b06", "#2e1610", "#683321", "#ff8a55", "#d9b6a8",
                       "Armor resists up, thermal down"),
    "Gamma": Theme("#0a1a0d", "#132a17", "#2f5a35", "#a6ea6f", "#b3cfb5",
                   "Shield resists up, explosive down"),
}
INCURSION_THEME = Theme("#07141c", "#0f2230", "#25475e", "#6cc4ff", "#a9c4d4")
NEUTRAL_THEME = Theme("#100e16", "#1c1926", "#3b3550", "#ece6ff", "#b9b2cc")


def theme_for(kind, weather):
    """
    The theme for a session.

    Args:
        kind (str): ABYSS or INCURSION.
        weather (str | None): The abyss session's weather.

    Returns:
        Theme: The weather's theme for abyss sessions, the incursion theme for
        incursions, and the neutral theme when there is no known weather.
    """
    if kind == INCURSION:
        return INCURSION_THEME
    if kind == ABYSS and weather in WEATHER_THEMES:
        return WEATHER_THEMES[weather]
    return NEUTRAL_THEME
