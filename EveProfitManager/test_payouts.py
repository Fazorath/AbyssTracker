import os
import tempfile
import tkinter
import unittest
from datetime import timedelta

from core import INCURSION, Tracker
from journal import Payout
from theme import load_fonts


class IncursionPayoutPageTest(unittest.TestCase):
    """Feeds journal payouts to the Incursion page and checks the sites it logs."""

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
        sid = self.tracker.start_session(INCURSION)
        self.start = self.tracker.session(sid).started_at
        self.app = gui.App(self.tracker)
        self.addCleanup(self.app.destroy)
        self.app.update()
        self.page = self.app.pages["incursion"]
        self.page.auto_log.select()  # as if switched on, without starting the ESI poll

    def payout(self, journal_id, minutes_in, millions):
        return Payout(journal_id=journal_id, paid_at=self.start + timedelta(minutes=minutes_in), millions=millions)

    def test_new_payouts_are_logged_as_sites_and_announced(self):
        self.page.take_payouts([self.payout(1, 11, 31.5), self.payout(2, 23, 28.75)])
        session = self.tracker.session(self.page.session_id)
        self.assertEqual((session.runs, session.profit, session.minutes), (2, 60.25, 23))
        self.assertIn("2 sites", self.page.message.cget("text"))
        self.assertEqual(len([t for t in self.page.tiles.winfo_children() if t is not self.page.empty]), 2)

    def test_payouts_already_logged_say_nothing(self):
        self.page.take_payouts([self.payout(1, 11, 31.5)])
        self.page.message.configure(text="")
        self.page.take_payouts([self.payout(1, 11, 31.5)])
        self.assertEqual(self.page.message.cget("text"), "")

    def test_sites_cannot_be_logged_by_hand_while_payouts_come_from_eve(self):
        self.page.payout.insert(0, "31")
        self.page.minutes.insert(0, "12")
        self.page.log()  # its payout would log the same site a second time
        self.assertEqual(self.tracker.session(self.page.session_id).runs, 0)
        self.assertIn("logged from EVE", self.page.message.cget("text"))

    def test_does_nothing_while_the_switch_is_off(self):
        self.page.auto_log.deselect()
        self.page.take_payouts([self.payout(1, 11, 31.5)])
        self.assertEqual(self.tracker.session(self.page.session_id).runs, 0)


if __name__ == "__main__":
    unittest.main()
