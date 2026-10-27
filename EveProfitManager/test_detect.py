import os
import tempfile
import tkinter
import unittest
from unittest import mock

from core import ABYSS, Tracker
from theme import load_fonts


class AbyssDetectionTest(unittest.TestCase):
    """Feeds location readings to the Abyss page and checks the timer and prompt."""

    def setUp(self):
        load_fonts()  # as the app does, before the first Tk: macOS reads the font list only then
        try:
            tkinter.Tk().destroy()
        except tkinter.TclError as err:  # no display, e.g. headless Linux CI
            self.skipTest(f"Tk cannot open a window: {err}")
        import customtkinter as ctk
        import gui

        ctk.set_appearance_mode("dark")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tracker = Tracker(os.path.join(folder.name, "tracker.db"))
        self.addCleanup(self.tracker.close)
        self.tracker.start_session(ABYSS, weather="Gamma", tier=2)
        self.app = gui.App(self.tracker)
        self.addCleanup(self.app.destroy)
        self.app.update()
        self.page = self.app.pages["abyss"]
        self.page.detect.select()  # as if switched on, without starting the ESI poll

    def test_entering_the_abyss_starts_the_timer_from_the_top(self):
        self.page.see_abyss(False)
        self.page.see_abyss(True)
        self.assertTrue(self.page.timer.running)
        self.assertEqual(self.page.timer.face().text, "20:00")

    def test_leaving_pauses_the_timer_and_prompts_to_log_the_run(self):
        self.page.see_abyss(False)
        self.page.see_abyss(True)
        self.page.timer.elapsed_before = 7 * 60  # pretend 7 minutes passed
        with mock.patch.object(self.page.cargo_after, "focus_set") as focus:
            self.page.see_abyss(False)
        focus.assert_called_once()
        self.assertFalse(self.page.timer.running)
        self.assertIn("13:00", self.page.message.cget("text"))
        self.assertIn("log", self.page.message.cget("text").lower())
        self.assertIn("cargo after", self.page.message.cget("text").lower())

    def test_the_paused_timer_time_is_what_gets_logged(self):
        self.page.see_abyss(False)
        self.page.see_abyss(True)
        self.page.timer.elapsed_before = 8 * 60
        self.page.see_abyss(False)
        self.page.cargo_before.insert(0, "100")
        self.page.cargo_after.insert(0, "144.5")
        self.page.log()
        run = self.tracker.runs(self.page.session_id)[0]
        self.assertEqual(run.minutes, 8)

    def test_does_nothing_while_detection_is_off(self):
        self.page.detect.deselect()
        self.page.see_abyss(False)
        self.page.see_abyss(True)
        self.assertFalse(self.page.timer.running)


if __name__ == "__main__":
    unittest.main()
