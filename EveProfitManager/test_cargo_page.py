import os
import tempfile
import tkinter
import unittest
from unittest import mock

from core import ABYSS, Tracker
from theme import load_fonts


class AbyssCargoFormTest(unittest.TestCase):
    """Drives the Abyss page's start and log forms by hand, signed out, as a user would."""

    def setUp(self):
        load_fonts()  # as the app does, before the first Tk: macOS reads the font list only then
        try:
            tkinter.Tk().destroy()
        except tkinter.TclError as err:  # no display, e.g. headless Linux CI
            self.skipTest(f"Tk cannot open a window: {err}")
        import customtkinter as ctk
        import gui

        self.gui = gui
        ctk.set_appearance_mode("dark")
        signed_out = mock.patch.object(gui.Account, "client", return_value=None)
        signed_out.start()
        self.addCleanup(signed_out.stop)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = os.path.join(folder.name, "tracker.db")
        self.tracker = Tracker(self.path)
        self.addCleanup(self.tracker.close)

    def open_app(self):
        self.app = self.gui.App(self.tracker)
        self.addCleanup(self.app.destroy)
        self.app.update()
        self.page = self.app.pages["abyss"]
        return self.page

    def texts(self, widget):
        """Text of every label under a widget."""
        found = []
        for child in widget.winfo_children():
            if isinstance(child, self.gui.ctk.CTkLabel):
                found.append(child.cget("text"))
            found.extend(self.texts(child))
        return found

    def type_run(self, before, after, left):
        for entry, text in ((self.page.cargo_before, before), (self.page.cargo_after, after),
                            (self.page.time_left, left)):
            self.gui.set_entry(entry, text)
        self.page.log()

    def test_starting_a_session_asks_for_the_filament_only(self):
        page = self.open_app()
        labels = self.texts(page.start_form)
        self.assertEqual(labels[:2], ["Tier", "Weather"])
        self.assertFalse(any("wallet" in text.lower() for text in labels))
        self.assertNotIn("wallet", page.subtitle.lower())
        page.weather.pick("Exotic")
        page.start_session()
        session = self.tracker.session(page.session_id)
        self.assertEqual((session.weather, session.starting_isk), ("Exotic", None))
        self.assertEqual(page.cargo_before.get(), "")

    def test_logs_a_run_from_typed_cargo_and_moves_cargo_after_into_cargo_before(self):
        sid = self.tracker.start_session(ABYSS, weather="Gamma", tier=2)
        page = self.open_app()
        self.assertEqual(self.texts(page.log_form)[:3], ["Cargo before (M)", "Cargo after (M)", "Time left (min)"])
        with mock.patch.object(page.cargo_after, "focus_set") as focus:
            self.type_run("120", "1,164.5", "6")
        run = self.tracker.runs(sid)[0]
        self.assertAlmostEqual(run.profit, 1044.5)
        self.assertEqual(run.minutes, 14)
        self.assertEqual((page.cargo_before.get(), page.cargo_after.get(), page.time_left.get()),
                         ("1164.5", "", ""))
        focus.assert_called_once()  # cargo before is filled in, so the cursor waits in cargo after
        self.assertIn("+1.04B", page.message.cget("text"))

    def test_a_loss_is_logged_and_a_bad_value_logs_nothing(self):
        sid = self.tracker.start_session(ABYSS, weather="Gamma", tier=2)
        page = self.open_app()
        self.type_run("200", "lots", "6")
        self.assertEqual(self.tracker.runs(sid), [])
        self.assertIn("cargo after", page.message.cget("text"))
        self.type_run("200", "150", "6")
        self.assertEqual(self.tracker.runs(sid)[0].profit, -50)

    def test_resuming_prefills_cargo_before_from_the_latest_cargo_run(self):
        sid = self.tracker.start_session(ABYSS, weather="Gamma", tier=2)
        self.tracker.log_cargo_run(sid, 10, 1234.5678, time_left=5)
        page = self.open_app()
        self.assertEqual(page.cargo_before.get(), "1234.5678")

    def test_resuming_a_wallet_only_session_leaves_cargo_before_empty(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000, weather="Gamma", tier=2)
        self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)
        page = self.open_app()
        self.assertEqual(page.cargo_before.get(), "")
        self.type_run("0", "40", "10")
        self.assertEqual([r.profit for r in self.tracker.runs(sid)], [30, 40])

    def open_edit(self, run):
        self.page.edit_run(run.id)
        self.app.update()
        (dialog,) = [w for w in self.page.winfo_children() if isinstance(w, self.gui.EditRunDialog)]
        return dialog

    def test_editing_a_cargo_run_shows_its_cargo_prefilled_and_saving_updates_the_session(self):
        sid = self.tracker.start_session(ABYSS, weather="Gamma", tier=2)
        first = self.tracker.log_cargo_run(sid, 100, 1310, time_left=5)  # meant 131
        last = self.tracker.log_cargo_run(sid, 1310, 1400, time_left=6)
        page = self.open_app()
        dialog = self.open_edit(first)
        self.assertEqual(self.texts(dialog)[:3], ["Cargo before (M)", "Cargo after (M)", "Time left (min)"])
        self.assertEqual([e.get() for e in dialog.entries], ["100", "1310", "5"])
        self.gui.set_entry(dialog.entries[1], "131")
        dialog.save()
        self.app.update()
        edited = self.tracker.run(first.id)
        self.assertEqual((edited.cargo_after, edited.profit), (131, 31))
        self.assertEqual(self.tracker.run(last.id), last)
        self.assertEqual(page.stats["profit"].value.cget("text"), self.gui.signed_isk(31 + 90))

    def test_a_bad_cargo_edit_keeps_the_dialog_open_and_changes_nothing(self):
        sid = self.tracker.start_session(ABYSS, weather="Gamma", tier=2)
        run = self.tracker.log_cargo_run(sid, 100, 131, time_left=5)
        self.open_app()
        dialog = self.open_edit(run)
        self.gui.set_entry(dialog.entries[2], "25")
        dialog.save()
        self.assertIn("between 0 and 20", dialog.message.cget("text"))
        self.assertEqual(self.tracker.run(run.id), run)

    def test_an_old_wallet_run_keeps_the_wallet_edit_dialog(self):
        sid = self.tracker.start_session(ABYSS, starting_isk=1000, weather="Gamma", tier=2)
        run = self.tracker.log_abyss_run(sid, 1000, 1030, time_left=10)
        self.open_app()
        dialog = self.open_edit(run)
        self.assertEqual(self.texts(dialog)[:2], ["Wallet after run (M)", "Time left (min)"])

    def test_settings_copy_no_longer_asks_for_the_wallet_for_abyssal_runs(self):
        self.open_app()
        copy = " ".join(self.texts(self.app.pages["settings"]))
        self.assertIn("wallet balance", copy)
        self.assertNotIn("enter your wallet", copy.lower())


if __name__ == "__main__":
    unittest.main()
