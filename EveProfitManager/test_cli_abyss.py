import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import abyss
from core import Tracker


class CliAbyssTest(unittest.TestCase):
    """Drive the terminal Abyss tracker with scripted input against a temp database."""

    def setUp(self):
        self.dir = TemporaryDirectory()
        self.tracker = Tracker(Path(self.dir.name) / "test.db")

    def tearDown(self):
        self.tracker.close()
        self.dir.cleanup()

    def drive(self, answers):
        """Run the CLI with these answers. Returns (session, prompts asked, printed output)."""
        prompts = []
        answers = iter(answers)

        def fake_input(prompt=""):
            prompts.append(prompt)
            return next(answers)

        out = io.StringIO()
        with patch("builtins.input", fake_input), patch("abyss.clear"), redirect_stdout(out):
            session = abyss.abyssMain(self.tracker)
        return session, prompts, out.getvalue()

    def test_asks_for_the_filament_and_cargo_not_a_wallet(self):
        session, prompts, _ = self.drive(["1", "1", "100", "130", "5", "0"])
        asked = " ".join(prompts).lower()
        self.assertNotIn("isk total", asked)
        self.assertNotIn("wallet", asked)
        self.assertIn("weather", prompts[0].lower())
        self.assertIn("tier", prompts[1].lower())
        self.assertIn("cargo before", prompts[2].lower())
        self.assertIn("cargo after", prompts[3].lower())
        self.assertIn("time left", prompts[4].lower())
        self.assertIsNone(self.tracker.session(session.id).starting_isk)

    def test_first_run_has_no_cargo_before_default(self):
        _, prompts, _ = self.drive(["1", "1", "100", "130", "5", "0"])
        self.assertIn("Cargo before: ", prompts[2])  # no " [default]" hint

    def test_logs_a_cargo_run_with_profit_after_minus_before(self):
        session, _, out = self.drive(["1", "1", "100", "130", "5", "0"])
        [run] = self.tracker.runs(session.id)
        self.assertEqual((run.cargo_before, run.cargo_after), (100, 130))
        self.assertEqual(run.profit, 30)
        self.assertEqual(run.minutes, 15)
        self.assertIsNone(run.isk_after)
        self.assertIn("Cargo after", out)
        self.assertNotIn("New total", out)

    def test_cargo_before_defaults_to_the_last_cargo_after_on_enter(self):
        session, prompts, _ = self.drive(["1", "1", "100", "130", "5", "1", "", "90", "2", "0"])
        self.assertIn("Cargo before [130]: ", prompts[6])
        first, second = self.tracker.runs(session.id)
        self.assertEqual((second.cargo_before, second.cargo_after), (130, 90))
        self.assertEqual(second.profit, -40)

    def test_a_typed_cargo_before_overrides_the_default(self):
        session, _, _ = self.drive(["1", "1", "100", "130", "5", "1", "50", "90", "2", "0"])
        self.assertEqual(self.tracker.runs(session.id)[1].cargo_before, 50)

    def test_bad_input_is_asked_again(self):
        session, _, out = self.drive(
            ["1", "1", "lots", "", "100", "abc", "130", "x", "25", "-1", "5", "0"]
        )
        [run] = self.tracker.runs(session.id)
        self.assertEqual((run.cargo_before, run.cargo_after, run.minutes), (100, 130, 15))
        self.assertIn("Please enter a number", out)

    def test_the_cli_no_longer_logs_wallet_runs(self):
        with patch.object(Tracker, "log_abyss_run", side_effect=AssertionError("wallet run")):
            session, _, _ = self.drive(["1", "1", "100", "130", "5", "0"])
        self.assertEqual(session.runs, 1)


if __name__ == "__main__":
    unittest.main()
