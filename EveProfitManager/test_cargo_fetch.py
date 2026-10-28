import os
import tempfile
import tkinter
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from cargo import Cargo
from core import ABYSS, Tracker
from theme import load_fonts

READ_AT = datetime(2026, 10, 25, 18, 40).timestamp()


class FetchCargoFromEveTest(unittest.TestCase):
    """Drives the two Fetch from EVE buttons through gui.App with the cargo reader mocked."""

    def setUp(self):
        load_fonts()
        try:
            tkinter.Tk().destroy()
        except tkinter.TclError as err:
            self.skipTest(f"Tk cannot open a window: {err}")
        import customtkinter as ctk
        import gui

        self.gui = gui
        ctk.set_appearance_mode("dark")
        self.client = SimpleNamespace(character=SimpleNamespace(id=123))
        account = mock.patch.object(gui.Account, "client", side_effect=lambda: self.client)
        account.start()
        self.addCleanup(account.stop)
        self.cargo = mock.Mock(return_value=Cargo(millions=164.5678, unpriced=0, fetched_at=READ_AT))
        reader = mock.patch.object(gui, "get_cargo", self.cargo)
        reader.start()
        self.addCleanup(reader.stop)
        wallet = mock.patch.object(gui, "get_wallet", side_effect=RuntimeError("no wallet here"))
        wallet.start()
        self.addCleanup(wallet.stop)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tracker = Tracker(os.path.join(folder.name, "tracker.db"))
        self.addCleanup(self.tracker.close)
        self.tracker.start_session(ABYSS, weather="Gamma", tier=2)
        sync = mock.patch.object(gui.App, "run_async", lambda _app, work, done: self.finish(work, done))
        sync.start()
        self.addCleanup(sync.stop)
        self.app = gui.App(self.tracker)
        self.addCleanup(self.app.destroy)
        self.app.update()
        self.page = self.app.pages["abyss"]

    @staticmethod
    def finish(work, done):
        try:
            result = work()
        except Exception as error:
            done(None, error)
        else:
            done(result, None)

    def note(self, which):
        return getattr(self.page, f"{which}_note").cget("text")

    def test_each_button_fills_its_own_field_to_two_decimals_and_stamps_when_eve_answered(self):
        self.page.fetch_cargo("before")
        self.assertEqual(self.page.cargo_before.get(), "164.57")
        self.assertEqual(self.page.cargo_after.get(), "")
        self.assertIn("From EVE at 18:40", self.note("cargo_before"))
        self.assertEqual(self.note("cargo_after"), "")
        self.page.fetch_cargo("after")
        self.assertEqual(self.page.cargo_after.get(), "164.57")
        self.assertIn("From EVE at 18:40", self.note("cargo_after"))
        self.assertIn("up to an hour", self.note("cargo_after"))
        self.assertIn("edit", self.note("cargo_after"))

    def test_the_buttons_are_on_the_page_and_call_fetch(self):
        self.page.fetch_buttons["after"].invoke()
        self.assertEqual(self.page.cargo_after.get(), "164.57")
        self.page.fetch_buttons["before"].invoke()
        self.assertEqual(self.page.cargo_before.get(), "164.57")

    def test_names_the_unpriced_item_types(self):
        self.cargo.return_value = Cargo(millions=10.0, unpriced=2, fetched_at=READ_AT)
        self.page.fetch_cargo("after")
        self.assertIn("From EVE at 18:40 · 2 unpriced", self.note("cargo_after"))

    def test_an_error_shows_in_the_note_in_the_critical_colour_and_leaves_the_field_alone(self):
        self.gui.set_entry(self.page.cargo_after, "88")
        self.cargo.side_effect = ValueError("Unexpected ship response")
        self.page.fetch_cargo("after")
        self.assertEqual(self.page.cargo_after.get(), "88")
        self.assertIn("Unexpected ship response", self.note("cargo_after"))
        self.assertEqual(self.page.cargo_after_note.cget("text_color"), self.gui.CRITICAL_TEXT)

    def test_a_fetch_after_an_error_clears_the_error_colour(self):
        self.cargo.side_effect = ValueError("x")
        self.page.fetch_cargo("after")
        self.cargo.side_effect = None
        self.page.fetch_cargo("after")
        self.assertNotEqual(self.page.cargo_after_note.cget("text_color"), self.gui.CRITICAL_TEXT)

    def test_signed_out_fetch_says_to_sign_in_and_the_field_still_works_by_hand(self):
        self.client = None
        self.gui.set_entry(self.page.cargo_before, "10")
        self.page.fetch_cargo("before")
        self.cargo.assert_not_called()
        self.assertIn("Sign in", self.note("cargo_before"))
        self.assertEqual(self.page.cargo_before.get(), "10")
        self.assertEqual(self.page.cargo_before_note.cget("text_color"), self.gui.CRITICAL_TEXT)

    def test_logging_a_run_clears_the_notes(self):
        self.page.fetch_cargo("before")
        self.page.fetch_cargo("after")
        self.gui.set_entry(self.page.time_left, "5")
        self.page.log()
        self.assertEqual(self.note("cargo_before"), "")
        self.assertEqual(self.note("cargo_after"), "")


if __name__ == "__main__":
    unittest.main()
