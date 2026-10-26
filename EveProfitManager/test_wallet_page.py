import os
import tempfile
import tkinter
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from core import ABYSS, Tracker
from theme import load_fonts
from wallet import Wallet

READ_AT = datetime(2026, 10, 25, 18, 40).timestamp()


class AbyssWalletStatTest(unittest.TestCase):
    """Drives the Abyss page with a mocked account and wallet reader and checks the read-only Wallet stat."""

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
        self.client = SimpleNamespace(character=SimpleNamespace(id=123))
        account = mock.patch.object(gui.Account, "client", side_effect=lambda: self.client)
        account.start()
        self.addCleanup(account.stop)
        self.wallet = mock.Mock(return_value=Wallet(millions=1250.0, fetched_at=READ_AT))
        reader = mock.patch.object(gui, "get_wallet", self.wallet)
        reader.start()
        self.addCleanup(reader.stop)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tracker = Tracker(os.path.join(folder.name, "tracker.db"))
        self.addCleanup(self.tracker.close)
        self.tracker.start_session(ABYSS, starting_isk=1000, weather="Gamma", tier=2)
        sync = mock.patch.object(gui.App, "run_async", lambda _app, work, done: self.finish(work, done))
        sync.start()  # read on the spot, not on a thread
        self.addCleanup(sync.stop)
        self.app = gui.App(self.tracker)
        self.addCleanup(self.app.destroy)
        self.app.update()
        self.wallet.reset_mock()  # the app read the wallet once as it opened the open session
        self.page = self.app.pages["abyss"]

    @staticmethod
    def finish(work, done):
        try:
            result = work()
        except Exception as error:  # the app's run_async hands the error on the same way
            done(None, error)
        else:
            done(result, None)

    def shown(self):
        wallet = self.page.stats["wallet"]
        return wallet.value.cget("text"), wallet.sub.cget("text")

    def test_there_is_no_loot_stat_and_the_wallet_stat_is_there(self):
        self.assertEqual(list(self.page.stats), ["profit", "rate", "time", "wallet"])

    def test_shows_the_balance_from_eve_with_when_it_was_read(self):
        self.page.resume()
        value, sub = self.shown()
        self.assertEqual(value, "1.25B")
        self.assertEqual(sub, "from EVE at 18:40")

    def test_reads_again_after_each_logged_run(self):
        self.page.resume()
        self.wallet.return_value = Wallet(millions=1300.0, fetched_at=READ_AT)
        self.page.after_isk.insert(0, "1,050")
        self.page.time_left.insert(0, "10")
        self.page.log()
        self.assertEqual(self.wallet.call_count, 2)
        self.assertEqual(self.shown()[0], "1.30B")

    def test_reads_when_a_session_starts(self):
        self.tracker.end_session(self.page.session_id)
        self.page.resume()
        self.page.start_isk.insert(0, "1,000")
        self.page.start_session()
        self.assertEqual(self.wallet.call_count, 1)
        self.assertEqual(self.shown()[1], "from EVE at 18:40")

    def test_signed_out_shows_a_dash_with_a_hint(self):
        self.client = None
        self.page.resume()
        value, sub = self.shown()
        self.assertEqual(value, "—")
        self.assertIn("sign in", sub.lower())
        self.wallet.assert_not_called()

    def test_a_read_error_shows_in_the_sub_line_and_logging_still_works(self):
        self.wallet.side_effect = ValueError("ESI returned 403")
        self.page.resume()
        self.assertIn("403", self.shown()[1])
        self.page.after_isk.insert(0, "1,050")
        self.page.time_left.insert(0, "10")
        self.page.log()
        self.assertEqual(len(self.tracker.runs(self.page.session_id)), 1)
        self.assertIn("403", self.shown()[1])

    def test_no_asset_polling_while_a_session_is_open(self):
        with mock.patch.object(self.page, "after") as after:
            self.page.resume()
        scheduled = [call.args[0] for call in after.call_args_list if call.args]
        self.assertNotIn(5 * 60 * 1000, scheduled)
        self.assertFalse(hasattr(self.page, "LOOT_POLL_MS"))
        self.assertFalse(hasattr(self.page, "value_loot"))

    def test_the_session_end_summary_has_no_loot_line(self):
        self.assertNotIn("loot", self.page.end_note().lower())


if __name__ == "__main__":
    unittest.main()
