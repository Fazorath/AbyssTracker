import os
import tempfile
import tkinter
import unittest

from core import ABYSS, INCURSION, Tracker


class PocketOverlayTest(unittest.TestCase):
    """Drives the pocket overlay through its buttons, as a user would."""

    def setUp(self):
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
        self.session = self.tracker.start_session(ABYSS, starting_isk=1000, weather="Gamma", tier=2)
        self.app = gui.App(self.tracker)
        self.addCleanup(self.app.destroy)
        self.app.update()

    def enter(self):
        self.app.enter_pocket()
        self.app.update()
        return self.app.pocket

    def test_opens_on_top_in_place_of_the_main_window(self):
        pocket = self.enter()
        self.assertEqual(self.app.state(), "withdrawn")
        self.assertTrue(pocket.attributes("-topmost"))

    def test_logs_a_run_from_the_wallet_using_the_shared_timer(self):
        pocket = self.enter()
        pocket.toggle_btn.invoke()
        self.assertTrue(self.app.pages["abyss"].timer.running)
        self.app.pages["abyss"].timer.elapsed_before = 8 * 60  # pretend 8 minutes passed

        pocket.amount.insert(0, "1,044.5")
        pocket.log_btn.invoke()

        runs = self.tracker.runs(self.session)
        self.assertEqual(len(runs), 1)
        self.assertAlmostEqual(runs[0].profit, 44.5)
        self.assertAlmostEqual(runs[0].minutes, 8, places=1)
        self.assertEqual(pocket.amount.get(), "")
        self.assertFalse(self.app.pages["abyss"].timer.running)  # reset for the next run
        self.assertIn("+44.5", pocket.message.cget("text"))

    def test_logging_without_the_timer_explains_and_logs_nothing(self):
        pocket = self.enter()
        pocket.amount.insert(0, "1100")
        pocket.log_btn.invoke()
        self.assertEqual(self.tracker.runs(self.session), [])
        self.assertIn("timer", pocket.message.cget("text"))

    def test_a_bad_value_leaves_the_full_window_form_as_it_was(self):
        page = self.app.pages["abyss"]
        page.after_isk.insert(0, "1,200")
        page.time_left.insert(0, "6")
        pocket = self.enter()
        pocket.toggle_btn.invoke()
        pocket.amount.delete(0, "end")
        pocket.amount.insert(0, "lots")
        pocket.log_btn.invoke()
        self.assertEqual(self.tracker.runs(self.session), [])
        self.assertIn("number", pocket.message.cget("text"))
        self.assertEqual((page.after_isk.get(), page.time_left.get()), ("1,200", "6"))

    def test_expand_keeps_a_value_typed_but_not_logged(self):
        pocket = self.enter()
        pocket.amount.insert(0, "1,300")
        pocket.expand_btn.invoke()
        self.assertEqual(self.app.pages["abyss"].after_isk.get(), "1,300")

    def test_a_running_timer_past_zero_still_offers_pause(self):
        pocket = self.enter()
        pocket.toggle_btn.invoke()
        self.app.pages["abyss"].timer.elapsed_before = 21 * 60
        self.app.after(300)  # wait out a tick of both timers
        self.app.update()
        self.assertEqual(pocket.toggle_btn.cget("text"), "Pause timer")
        self.assertEqual(self.app.pages["abyss"].timer.toggle_btn.cget("text"), "Pause timer")

    def test_pin_button_toggles_always_on_top(self):
        # Without a window manager (Xvfb), -topmost can't be cleared, so read the overlay's own state
        pocket = self.enter()
        pocket.pin_btn.invoke()
        self.assertFalse(pocket.pinned)
        self.assertEqual(pocket.pin_btn.cget("text"), "Pin on top")
        pocket.pin_btn.invoke()
        self.assertTrue(pocket.pinned)
        self.assertTrue(pocket.attributes("-topmost"))
        self.assertEqual(pocket.pin_btn.cget("text"), "Unpin")

    def test_incursion_tab_logs_a_site_at_the_saved_payout(self):
        self.tracker.set_setting("incursion_payout", "31")
        site_session = self.tracker.start_session(INCURSION)
        self.app.pages["incursion"].resume()
        pocket = self.enter()
        pocket.tabs[INCURSION].invoke()
        self.assertEqual(pocket.amount.get(), "31")
        self.app.pages["incursion"].timer.elapsed_before = 12 * 60

        pocket.log_btn.invoke()

        runs = self.tracker.runs(site_session)
        self.assertEqual(len(runs), 1)
        self.assertAlmostEqual(runs[0].profit, 31)
        self.assertEqual(pocket.amount.get(), "31")  # the payout stays for the next site

    def test_expand_closes_the_overlay_and_brings_back_the_window(self):
        pocket = self.enter()
        pocket.expand_btn.invoke()
        self.app.update()
        self.assertIsNone(self.app.pocket)
        self.assertEqual(self.app.state(), "normal")


if __name__ == "__main__":
    unittest.main()
