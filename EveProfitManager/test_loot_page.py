import os
import tempfile
import tkinter
import unittest
from datetime import datetime
from unittest import mock

from core import ABYSS, Tracker
from loot import Assets
from theme import load_fonts

READ_AT = datetime(2026, 10, 25, 18, 40).timestamp()


class AbyssLootPageTest(unittest.TestCase):
    """Feeds asset readings to the Abyss page and checks the unsold loot it shows."""

    def setUp(self):
        load_fonts()  # as the app does, before the first Tk: macOS reads the font list only then
        try:
            tkinter.Tk().destroy()
        except tkinter.TclError as err:  # no display, e.g. headless Linux CI
            self.skipTest(f"Tk cannot open a window: {err}")
        import customtkinter as ctk
        import gui

        ctk.set_appearance_mode("dark")
        signed_out = mock.patch.object(gui.Account, "client", return_value=None)  # keep the real account's ESI out
        signed_out.start()
        self.addCleanup(signed_out.stop)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tracker = Tracker(os.path.join(folder.name, "tracker.db"))
        self.addCleanup(self.tracker.close)
        self.tracker.start_session(ABYSS, starting_isk=1000, weather="Gamma", tier=2)
        self.app = gui.App(self.tracker)
        self.addCleanup(self.app.destroy)
        self.app.update()
        self.page = self.app.pages["abyss"]
        self.loot = self.page.stats["loot"]

    def shown(self):
        return self.loot.value.cget("text"), self.loot.sub.cget("text")

    def test_shows_the_value_of_what_came_back_beside_the_wallet_profit(self):
        self.page.take_assets(Assets({34: 10_000, 47_762: 1}, READ_AT), None)  # at the session start
        self.page.take_assets(Assets({34: 10_000, 49_000: 2}, READ_AT), {47_762: 1_200_000.0, 49_000: 2_100_000.0})
        value, sub = self.shown()
        self.assertEqual(value, "+3.0M")
        self.assertIn("18:40", sub)
        self.assertEqual(self.page.stats["profit"].value.cget("text"), "0.0M")  # the wallet hasn't changed

    def test_says_how_many_kinds_of_item_have_no_price(self):
        self.page.take_assets(Assets({}, READ_AT), None)
        self.page.take_assets(Assets({52_227: 1, 52_228: 1}, READ_AT), {})
        self.assertIn("2 unpriced", self.shown()[1])

    def test_waits_for_the_first_reading_before_valuing_anything(self):
        self.page.take_assets(Assets({34: 10_000}, READ_AT), None)
        self.assertEqual(self.shown()[0], "0.0M")
        self.assertIsNone(self.tracker.loot(self.page.session_id))


if __name__ == "__main__":
    unittest.main()
