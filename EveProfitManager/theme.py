"""
Filament theme: colour tokens per abyssal weather, used by the desktop UI.
"""
import ctypes
import ctypes.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from core import ABYSS, INCURSION

# Icon and other files the UI loads; PyInstaller bundles this folder next to the code
ASSETS = Path(__file__).resolve().parent / "assets"


def asset_path(name):
    """Absolute path of a file in the assets folder."""
    return str(ASSETS / name)


# UI typeface, bundled under the SIL Open Font License (assets/fonts/OFL.txt)
FONT_FAMILY = "Chakra Petch"
FONT_FILES = [asset_path("fonts/ChakraPetch-Regular.ttf"), asset_path("fonts/ChakraPetch-Bold.ttf")]


def load_fonts():
    """
    Register the bundled font files for this process only, so nothing is installed.

    Call before creating the Tk window, which reads the font list when it starts.

    Returns:
        bool: True when every file registered. Tk can still fall back to another
        family when this fails, so the UI decides with ui_family().
    """
    try:
        return all(_register_font(path) for path in FONT_FILES)
    except (OSError, AttributeError):  # missing system library or symbol
        return False


def _register_font(path):
    if sys.platform == "win32":
        FR_PRIVATE = 0x10  # visible to this process only, but still listed by Tk
        return ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0) > 0

    if sys.platform == "darwin":
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        ct = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
        cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
        cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool]
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
        ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        raw = os.fsencode(path)
        url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
        if not url:
            return False
        try:
            PROCESS_SCOPE = 1  # kCTFontManagerScopeProcess
            return ct.CTFontManagerRegisterFontsForURL(url, PROCESS_SCOPE, None)
        finally:
            cf.CFRelease(url)

    # Linux and other X11 systems: Tk draws through fontconfig (Xft)
    name = ctypes.util.find_library("fontconfig")
    if not name:
        return False
    fontconfig = ctypes.CDLL(name)
    fontconfig.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    return bool(fontconfig.FcConfigAppFontAddFile(None, os.fsencode(path)))


def ui_family(available, fallback):
    """
    The font family the UI draws with.

    Args:
        available (Iterable[str]): Families Tk can use (tkinter.font.families()).
        fallback (str): Family to use when the bundled font did not load.

    Returns:
        str: FONT_FAMILY when Tk has it, otherwise fallback.
    """
    return FONT_FAMILY if FONT_FAMILY in available else fallback


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
