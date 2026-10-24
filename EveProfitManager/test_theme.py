import os
import tkinter
import tkinter.font
import unittest

from core import ABYSS, INCURSION, WEATHERS
from theme import FONT_FAMILY, FONT_FILES, asset_path, load_fonts, theme_for, ui_family


class ThemeTest(unittest.TestCase):
    def test_abyss_session_takes_its_weather_theme(self):
        firestorm = theme_for(ABYSS, "Firestorm")
        self.assertEqual(firestorm.bg, "#1d0b06")
        self.assertEqual(firestorm.accent, "#ff8a55")
        self.assertEqual(firestorm.hint, "Armor resists up, thermal down")
        self.assertEqual(theme_for(ABYSS, "Gamma").accent, "#a6ea6f")

    def test_every_weather_has_its_own_theme(self):
        themes = [theme_for(ABYSS, w) for w in WEATHERS]
        self.assertEqual(len({t.bg for t in themes}), len(WEATHERS))
        self.assertTrue(all(t.hint for t in themes))

    def test_incursion_ignores_weather(self):
        incursion = theme_for(INCURSION, None)
        self.assertEqual(incursion.accent, "#6cc4ff")
        self.assertEqual(theme_for(INCURSION, "Gamma"), incursion)
        self.assertEqual(incursion.hint, "")

    def test_abyss_without_weather_gets_neutral_theme(self):
        neutral = theme_for(ABYSS, None)
        self.assertEqual(neutral.bg, "#100e16")
        self.assertEqual(neutral.hint, "")
        self.assertEqual(theme_for(ABYSS, "Hail"), neutral)
        self.assertEqual(theme_for(None, None), neutral)

    def test_asset_path_finds_the_bundled_icon(self):
        for name in ("icon.png", "icon.ico", "icon.icns"):
            self.assertTrue(os.path.isfile(asset_path(name)), name)

    def test_ui_font_and_its_licence_are_bundled(self):
        for path in FONT_FILES + [asset_path("fonts/OFL.txt")]:
            self.assertTrue(os.path.isfile(path), path)
        self.assertEqual(len(FONT_FILES), 2)

    def test_ui_family_uses_chakra_petch_when_tk_has_it(self):
        self.assertEqual(ui_family(("Helvetica", "Chakra Petch"), "Roboto"), "Chakra Petch")

    def test_ui_family_falls_back_when_the_font_did_not_load(self):
        self.assertEqual(ui_family(("Helvetica", "Arial"), "Roboto"), "Roboto")
        self.assertEqual(ui_family((), "Roboto"), "Roboto")

    def test_load_fonts_makes_chakra_petch_available_to_tk(self):
        self.assertTrue(load_fonts())
        try:
            root = tkinter.Tk()
        except tkinter.TclError as err:  # no display, e.g. headless Linux CI
            self.skipTest(f"Tk cannot open a window: {err}")
        try:
            self.assertIn(FONT_FAMILY, tkinter.font.families(root))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
