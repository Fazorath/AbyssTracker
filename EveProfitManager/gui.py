"""
Desktop UI for the Abyss and Incursion tracker.

Run with:  python gui.py
"""
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import (
    ABYSS,
    INCURSION,
    MAXTIME,
    Tracker,
    format_isk,
    format_minutes,
    isk_per_hour,
)

# Dark theme tokens
PAGE = "#0d0d0d"
SURFACE = "#1a1a19"
RAISED = "#242422"
BORDER = "#2c2c2a"
AXIS = "#383835"
INK = "#f0efec"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GOOD = "#0ca30c"
WARNING = "#fab219"
CRITICAL = "#d03b3b"
GOOD_TEXT = "#3fcf5e"
CRITICAL_TEXT = "#ec6b6b"

KIND_COLOR = {ABYSS: "#d95926", INCURSION: "#3987e5"}
KIND_HOVER = {ABYSS: "#b8481c", INCURSION: "#2c6fc0"}
KIND_NAME = {ABYSS: "Abyss", INCURSION: "Incursion"}


def parse_isk(text, field="value"):
    """
    Parse an ISK amount in millions. Accepts '31', '31.5m', '1,250', '1.2b', '800k'.

    Args:
        text (str): What the user typed.
        field (str): Field name used in the error message.

    Returns:
        float: Amount in millions.
    """
    raw = text.strip().lower().replace(",", "").replace(" ", "").removesuffix("isk")
    scale = {"b": 1000.0, "m": 1.0, "k": 0.001}.get(raw[-1:], None)
    if scale is not None:
        raw = raw[:-1]
    try:
        return float(raw) * (scale or 1.0)
    except ValueError:
        raise ValueError(f"Enter a number for {field} (e.g. 31.5, 1.2b, 800k)") from None


def parse_minutes(text, field="time"):
    """Parse minutes, also accepting 'mm:ss'."""
    raw = text.strip()
    try:
        if ":" in raw:
            mins, secs = raw.split(":", 1)
            return int(mins) + int(secs) / 60
        return float(raw)
    except ValueError:
        raise ValueError(f"Enter minutes for {field} (e.g. 14.5 or 14:30)") from None


def signed_isk(millions):
    return ("+" if millions > 0 else "") + format_isk(millions)


def profit_color(millions):
    return GOOD_TEXT if millions > 0 else CRITICAL_TEXT if millions < 0 else INK_2


def font(size=13, weight="normal"):
    return ctk.CTkFont(size=size, weight=weight)


class StatCard(ctk.CTkFrame):
    """A small tile with a label and a big number."""

    def __init__(self, master, label):
        super().__init__(master, fg_color=SURFACE, corner_radius=10, border_width=1, border_color=BORDER)
        ctk.CTkLabel(self, text=label.upper(), font=font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=16, pady=(12, 0)
        )
        self.value = ctk.CTkLabel(self, text="—", font=font(24, "bold"), text_color=INK)
        self.value.pack(anchor="w", padx=16)
        self.sub = ctk.CTkLabel(self, text="", font=font(11), text_color=MUTED, height=16)
        self.sub.pack(anchor="w", padx=16, pady=(0, 10))

    def set(self, value, color=INK, sub=""):
        self.value.configure(text=value, text_color=color)
        self.sub.configure(text=sub)


class TimerPanel(ctk.CTkFrame):
    """
    A countdown (for the abyssal timer) or a stopwatch (for incursion sites).

    When the time field is left blank, the page uses this timer's value.
    """

    def __init__(self, master, title, accent, countdown_minutes=None):
        super().__init__(master, fg_color=RAISED, corner_radius=10)
        self.countdown = countdown_minutes * 60 if countdown_minutes else None
        self.elapsed_before = 0.0
        self.started = None
        self._job = None

        ctk.CTkLabel(self, text=title.upper(), font=font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=16, pady=(12, 0)
        )
        self.display = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Consolas", size=40, weight="bold"))
        self.display.pack(anchor="w", padx=16)
        self.hint = ctk.CTkLabel(self, text="", font=font(11), text_color=MUTED, height=16)
        self.hint.pack(anchor="w", padx=16)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(anchor="w", padx=12, pady=(6, 12))
        self.toggle_btn = ctk.CTkButton(
            buttons, text="Start", width=90, fg_color=accent[0], hover_color=accent[1], command=self.toggle
        )
        self.toggle_btn.pack(side="left", padx=4)
        ctk.CTkButton(
            buttons, text="Reset", width=70, fg_color="transparent", border_width=1,
            border_color=AXIS, hover_color=BORDER, text_color=INK_2, command=self.reset,
        ).pack(side="left", padx=4)
        self._render()

    @property
    def running(self):
        return self.started is not None

    def elapsed(self):
        return self.elapsed_before + (time.monotonic() - self.started if self.running else 0)

    def value_minutes(self):
        """Minutes left (countdown) or elapsed (stopwatch); None if the timer was never started."""
        elapsed = self.elapsed()
        if elapsed <= 0:
            return None
        if self.countdown:
            return round(max(0.0, self.countdown - elapsed) / 60, 2)
        return round(elapsed / 60, 2)

    def toggle(self):
        if self.running:
            self.elapsed_before = self.elapsed()
            self.started = None
        else:
            self.started = time.monotonic()
            self._tick()
        self._render()

    def reset(self):
        self.started = None
        self.elapsed_before = 0.0
        self._render()

    def _tick(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        if self.running:
            self._render()
            self._job = self.after(250, self._tick)

    def _render(self):
        elapsed = self.elapsed()
        seconds = max(0.0, self.countdown - elapsed) if self.countdown else elapsed
        mins, secs = divmod(int(seconds + (0.999 if self.countdown else 0)), 60)
        color = INK
        if self.countdown and elapsed > 0:
            if seconds <= 0:
                color = CRITICAL_TEXT
            elif seconds < 120:
                color = CRITICAL_TEXT
            elif seconds < 300:
                color = WARNING
        self.display.configure(text=f"{mins:02d}:{secs:02d}", text_color=color)

        if self.countdown and elapsed > 0 and seconds <= 0:
            hint = "Timer expired"
        elif elapsed > 0:
            hint = "Leave the time field blank to use this"
        else:
            hint = "Start when you enter" if self.countdown else "Start when the site starts"
        self.hint.configure(text=hint)
        self.toggle_btn.configure(text="Pause" if self.running else ("Resume" if elapsed > 0 else "Start"))


class RunLog(ctk.CTkFrame):
    """Table of the runs/sites in the current session, newest first."""

    def __init__(self, master, columns, on_delete):
        super().__init__(master, fg_color=SURFACE, corner_radius=10, border_width=1, border_color=BORDER)
        self.columns = columns  # list of (heading, width, anchor)
        self.on_delete = on_delete
        header = ctk.CTkFrame(self, fg_color="transparent", height=32)
        header.pack(fill="x", padx=12, pady=(10, 0))
        self._layout(header)
        for i, (heading, _, anchor) in enumerate(columns):
            ctk.CTkLabel(header, text=heading.upper(), font=font(11, "bold"), text_color=MUTED, anchor=anchor).grid(
                row=0, column=i, sticky="ew", padx=6
            )
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", padx=12, pady=(4, 0))
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self.empty = ctk.CTkLabel(self.body, text="", text_color=MUTED, font=font(13))

    def _layout(self, frame):
        for i, (_, width, _) in enumerate(self.columns):
            frame.grid_columnconfigure(i, minsize=width, weight=1 if width == 0 else 0)
        frame.grid_columnconfigure(len(self.columns), minsize=36)

    def show(self, rows, empty_text):
        """
        Args:
            rows (list[tuple[int, list[tuple[str, str]]]]): (run id, [(text, color), ...]) per row.
            empty_text (str): Shown when there are no rows.
        """
        for child in self.body.winfo_children():
            if child is not self.empty:
                child.destroy()
        if not rows:
            self.empty.configure(text=empty_text)
            self.empty.pack(pady=30)
            return
        self.empty.pack_forget()
        for run_id, cells in rows:
            row = ctk.CTkFrame(self.body, fg_color="transparent", height=34)
            row.pack(fill="x", padx=8)
            self._layout(row)
            for i, (text, color) in enumerate(cells):
                ctk.CTkLabel(row, text=text, text_color=color, font=font(13), anchor=self.columns[i][2]).grid(
                    row=0, column=i, sticky="ew", padx=6, pady=3
                )
            ctk.CTkButton(
                row, text="×", width=28, height=24, fg_color="transparent", hover_color=BORDER,
                text_color=MUTED, command=lambda r=run_id: self.on_delete(r),
            ).grid(row=0, column=len(cells), padx=(4, 0))


class SessionPage(ctk.CTkFrame):
    """
    Shared layout for the Abyss and Incursion pages: a start screen and a live session screen.
    """

    kind = None
    title = ""
    subtitle = ""
    unit = "run"

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.tracker = app.tracker
        self.session_id = None
        self._message_job = None
        accent = KIND_COLOR[self.kind]

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text=self.title, font=font(26, "bold"), text_color=INK).pack(side="left")
        self.status = ctk.CTkLabel(header, text="", font=font(12), text_color=MUTED)
        self.status.pack(side="left", padx=14, pady=(8, 0))
        self.end_btn = ctk.CTkButton(
            header, text="End session", width=120, fg_color="transparent", border_width=1,
            border_color=AXIS, hover_color=BORDER, text_color=INK, command=self.end_session,
        )

        # Start screen
        self.start_view = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=12, border_width=1, border_color=BORDER)
        inner = ctk.CTkFrame(self.start_view, fg_color="transparent")
        inner.pack(padx=40, pady=40, anchor="w")
        ctk.CTkLabel(inner, text="Start a session", font=font(20, "bold"), text_color=INK).pack(anchor="w")
        ctk.CTkLabel(inner, text=self.subtitle, font=font(13), text_color=INK_2, justify="left", wraplength=520).pack(
            anchor="w", pady=(4, 20)
        )
        self.start_form = ctk.CTkFrame(inner, fg_color="transparent")
        self.start_form.pack(anchor="w")
        self.build_start_form(self.start_form)
        ctk.CTkButton(
            inner, text="Start session", height=38, width=180, font=font(14, "bold"),
            fg_color=accent, hover_color=KIND_HOVER[self.kind], command=self.start_session,
        ).pack(anchor="w", pady=(20, 0))
        self.start_message = ctk.CTkLabel(inner, text="", text_color=CRITICAL_TEXT, font=font(12))
        self.start_message.pack(anchor="w", pady=(8, 0))

        # Live session screen
        self.live_view = ctk.CTkFrame(self, fg_color="transparent")
        cards = ctk.CTkFrame(self.live_view, fg_color="transparent")
        cards.pack(fill="x")
        self.cards = {}
        for i, (key, label) in enumerate(self.card_labels()):
            cards.grid_columnconfigure(i, weight=1, uniform="cards")
            self.cards[key] = StatCard(cards, label)
            self.cards[key].grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))

        middle = ctk.CTkFrame(self.live_view, fg_color="transparent")
        middle.pack(fill="x", pady=12)
        middle.grid_columnconfigure(0, weight=1)

        form_card = ctk.CTkFrame(middle, fg_color=SURFACE, corner_radius=10, border_width=1, border_color=BORDER)
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ctk.CTkLabel(form_card, text=f"LOG A {self.unit.upper()}", font=font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=16, pady=(12, 6)
        )
        self.log_form = ctk.CTkFrame(form_card, fg_color="transparent")
        self.log_form.pack(anchor="w", padx=16)
        self.build_log_form(self.log_form)
        actions = ctk.CTkFrame(form_card, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(12, 14))
        ctk.CTkButton(
            actions, text=f"Log {self.unit}  ⏎", height=36, width=150, font=font(14, "bold"),
            fg_color=accent, hover_color=KIND_HOVER[self.kind], command=self.log,
        ).pack(side="left")
        self.message = ctk.CTkLabel(actions, text="", font=font(12), text_color=MUTED)
        self.message.pack(side="left", padx=12)

        self.timer = self.build_timer(middle)
        self.timer.grid(row=0, column=1, sticky="nsew")

        self.log_table = RunLog(self.live_view, self.log_columns(), self.delete_run)
        self.log_table.pack(fill="both", expand=True)

        for entry in self.entries():
            entry.bind("<Return>", lambda _e: self.log())

    # --- hooks for subclasses ---------------------------------------------

    def build_start_form(self, frame): ...
    def build_log_form(self, frame): ...
    def build_timer(self, master): ...
    def entries(self): return []
    def card_labels(self): return []
    def log_columns(self): return []
    def start_args(self): return {}
    def log_run(self): ...
    def update_cards(self, session, runs): ...
    def run_cells(self, index, run): return []
    def after_log(self): ...

    # --- shared behaviour -------------------------------------------------

    def field(self, frame, column, label, width=170, placeholder=""):
        """Add a labelled entry to a form row and return the entry."""
        ctk.CTkLabel(frame, text=label, font=font(12), text_color=INK_2).grid(
            row=0, column=column, sticky="w", padx=(0, 12)
        )
        entry = ctk.CTkEntry(
            frame, width=width, height=36, font=font(15), placeholder_text=placeholder,
            fg_color=PAGE, border_color=AXIS,
        )
        entry.grid(row=1, column=column, sticky="w", padx=(0, 12), pady=(2, 0))
        return entry

    def resume(self):
        session = self.tracker.active_session(self.kind)
        self.session_id = session.id if session else None
        self.refresh()

    def start_session(self):
        try:
            args = self.start_args()
        except ValueError as err:
            self.start_message.configure(text=str(err))
            return
        self.start_message.configure(text="")
        self.session_id = self.tracker.start_session(self.kind, **args)
        self.app.refresh()
        self.entries()[0].focus_set()

    def end_session(self):
        session = self.tracker.session(self.session_id)
        if session.runs and not messagebox.askyesno(
            "End session",
            f"End this {KIND_NAME[self.kind].lower()} session?\n\n"
            f"{session.runs} {self.unit}s · {signed_isk(session.profit)} ISK · {format_minutes(session.minutes)}",
            parent=self,
        ):
            return
        self.tracker.end_session(self.session_id)
        self.session_id = None
        self.timer.reset()
        self.app.refresh()

    def log(self):
        if self.session_id is None:
            return
        try:
            run = self.log_run()
        except ValueError as err:
            self.flash(str(err), CRITICAL_TEXT)
            return
        self.timer.reset()
        self.after_log()
        self.flash(
            f"Logged {signed_isk(run.profit)} in {format_minutes(run.minutes)}",
            profit_color(run.profit),
        )
        self.app.refresh()
        self.entries()[0].focus_set()

    def timer_or(self, entry, field):
        """Value typed in a time entry, or the timer's value when the entry is blank."""
        if entry.get().strip():
            return parse_minutes(entry.get(), field)
        value = self.timer.value_minutes()
        if value is None:
            raise ValueError(f"Enter {field}, or use the timer")
        return value

    def delete_run(self, run_id):
        run = self.tracker.run(run_id)
        if run and messagebox.askyesno(
            f"Delete {self.unit}",
            f"Delete this {self.unit}? ({signed_isk(run.profit)} ISK, {format_minutes(run.minutes)})",
            parent=self,
        ):
            self.tracker.delete_run(run_id)
            self.app.refresh()

    def flash(self, text, color=MUTED):
        self.message.configure(text=text, text_color=color)
        if self._message_job:
            self.after_cancel(self._message_job)
        self._message_job = self.after(5000, lambda: self.message.configure(text=""))

    def refresh(self):
        session = self.tracker.session(self.session_id) if self.session_id else None
        if session is None:
            self.session_id = None
            self.live_view.pack_forget()
            self.end_btn.pack_forget()
            self.start_view.pack(fill="both", expand=True)
            self.status.configure(text="No active session", text_color=MUTED)
            return
        self.start_view.pack_forget()
        self.live_view.pack(fill="both", expand=True)
        self.end_btn.pack(side="right")
        self.status.configure(
            text=f"● Live since {session.started_at:%H:%M}  ·  {session.started_at:%a %d %b}", text_color=GOOD_TEXT
        )
        runs = self.tracker.runs(self.session_id)
        self.update_cards(session, runs)
        rows = [(run.id, self.run_cells(i + 1, run)) for i, run in reversed(list(enumerate(runs)))]
        self.log_table.show(rows, f"No {self.unit}s yet. Log your first one above.")


class AbyssPage(SessionPage):
    kind = ABYSS
    title = "Abyssal Deadspace"
    subtitle = (
        "Enter your wallet before the first run. After each run, enter the new wallet total and the "
        "time left on the 20-minute timer, or run the built-in timer and leave the time blank."
    )
    unit = "run"

    def build_start_form(self, frame):
        self.start_isk = self.field(frame, 0, "Wallet now (million ISK)", 220, "e.g. 1,250 or 1.25b")
        self.start_isk.bind("<Return>", lambda _e: self.start_session())

    def build_log_form(self, frame):
        self.after_isk = self.field(frame, 0, "Wallet after run (M)", 200, "e.g. 1,281")
        self.time_left = self.field(frame, 1, "Time left (min)", 130, "blank = timer")

    def build_timer(self, master):
        return TimerPanel(master, "Abyssal timer", (KIND_COLOR[ABYSS], KIND_HOVER[ABYSS]), countdown_minutes=MAXTIME)

    def entries(self):
        return [self.after_isk, self.time_left]

    def card_labels(self):
        return [("profit", "Session profit"), ("rate", "ISK / hour"), ("runs", "Runs"),
                ("time", "Time in abyss"), ("wallet", "Wallet")]

    def log_columns(self):
        return [("#", 40, "w"), ("Logged", 80, "w"), ("Wallet", 0, "e"), ("Profit", 120, "e"),
                ("Duration", 100, "e"), ("ISK / hr", 120, "e")]

    def start_args(self):
        return {"starting_isk": parse_isk(self.start_isk.get(), "your wallet")}

    def log_run(self):
        after = parse_isk(self.after_isk.get(), "wallet after")
        left = self.timer_or(self.time_left, "time left")
        before = self.tracker.current_isk(self.session_id)
        return self.tracker.log_abyss_run(self.session_id, before, after, left)

    def after_log(self):
        self.after_isk.delete(0, "end")
        self.time_left.delete(0, "end")

    def update_cards(self, session, runs):
        avg = session.profit / session.runs if session.runs else 0
        self.cards["profit"].set(signed_isk(session.profit), profit_color(session.profit),
                                 f"avg {signed_isk(avg)} / run" if runs else "")
        self.cards["rate"].set(format_isk(session.isk_per_hour), INK)
        self.cards["runs"].set(str(session.runs), INK,
                               f"avg {format_minutes(session.minutes / session.runs)}" if runs else "")
        self.cards["time"].set(format_minutes(session.minutes), INK)
        self.cards["wallet"].set(format_isk(self.tracker.current_isk(session.id) or 0), INK,
                                 f"started at {format_isk(session.starting_isk or 0)}")

    def run_cells(self, index, run):
        return [
            (str(index), MUTED),
            (f"{run.recorded_at:%H:%M}", INK_2),
            (format_isk(run.isk_after) if run.isk_after is not None else "—", INK_2),
            (signed_isk(run.profit), profit_color(run.profit)),
            (format_minutes(run.minutes), INK_2),
            (format_isk(isk_per_hour(run.profit, run.minutes)), INK),
        ]


class IncursionPage(SessionPage):
    kind = INCURSION
    title = "Incursions"
    subtitle = (
        "Set the payout per site; it's remembered for next time. Log each site with its time, "
        "or run the stopwatch and leave the time blank."
    )
    unit = "site"

    def build_start_form(self, frame):
        self.per_site = self.field(frame, 0, "Payout per site (million ISK)", 240, "e.g. 31")
        saved = self.tracker.get_setting("incursion_payout")
        if saved:
            self.per_site.insert(0, saved)
        self.per_site.bind("<Return>", lambda _e: self.start_session())

    def build_log_form(self, frame):
        self.payout = self.field(frame, 0, "Payout (M)", 130)
        self.minutes = self.field(frame, 1, "Site time (min)", 130, "blank = stopwatch")

    def build_timer(self, master):
        return TimerPanel(master, "Site stopwatch", (KIND_COLOR[INCURSION], KIND_HOVER[INCURSION]))

    def entries(self):
        return [self.minutes, self.payout]

    def card_labels(self):
        return [("profit", "Session profit"), ("rate", "ISK / hour"), ("runs", "Sites"),
                ("time", "Time running"), ("avg", "Avg site")]

    def log_columns(self):
        return [("#", 40, "w"), ("Logged", 80, "w"), ("Payout", 0, "e"),
                ("Duration", 100, "e"), ("ISK / hr", 120, "e")]

    def start_args(self):
        payout = parse_isk(self.per_site.get(), "payout per site")
        self.tracker.set_setting("incursion_payout", f"{payout:g}")
        self.payout.delete(0, "end")
        self.payout.insert(0, f"{payout:g}")
        return {}

    def resume(self):
        super().resume()
        if not self.payout.get():
            self.payout.insert(0, self.tracker.get_setting("incursion_payout", ""))

    def log_run(self):
        payout = parse_isk(self.payout.get(), "payout")
        minutes = self.timer_or(self.minutes, "site time")
        return self.tracker.log_incursion_site(self.session_id, payout, minutes)

    def after_log(self):
        self.minutes.delete(0, "end")

    def update_cards(self, session, runs):
        self.cards["profit"].set(signed_isk(session.profit), profit_color(session.profit))
        self.cards["rate"].set(format_isk(session.isk_per_hour), INK)
        self.cards["runs"].set(str(session.runs), INK)
        self.cards["time"].set(format_minutes(session.minutes), INK)
        self.cards["avg"].set(format_minutes(session.minutes / session.runs) if session.runs else "—", INK)

    def run_cells(self, index, run):
        return [
            (str(index), MUTED),
            (f"{run.recorded_at:%H:%M}", INK_2),
            (signed_isk(run.profit), profit_color(run.profit)),
            (format_minutes(run.minutes), INK_2),
            (format_isk(isk_per_hour(run.profit, run.minutes)), INK),
        ]


class ProfitChart(tk.Canvas):
    """Bar chart of profit per session, oldest to newest, with a hover tooltip."""

    PAD_L, PAD_R, PAD_T, PAD_B = 64, 16, 16, 28

    def __init__(self, master):
        super().__init__(master, bg=SURFACE, highlightthickness=0, height=240)
        self.sessions = []
        self.bars = []  # (x0, x1, session)
        self.bind("<Configure>", lambda _e: self.draw())
        self.bind("<Motion>", self._hover)
        self.bind("<Leave>", lambda _e: self.delete("tip"))

    def show(self, sessions):
        self.sessions = list(reversed(sessions[:40]))
        self.draw()

    def draw(self):
        self.delete("all")
        self.bars = []
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        if not self.sessions:
            self.create_text(w / 2, h / 2, text="No sessions yet", fill=MUTED, font=("TkDefaultFont", 11))
            return
        top = max(0.0, max(s.profit for s in self.sessions))
        bottom = min(0.0, min(s.profit for s in self.sessions))
        step = _nice_step((top - bottom) or 1)
        top = step * -(-top // step) if top else 0
        bottom = step * (bottom // step) if bottom else 0
        if top == bottom:
            top = step
        plot_h = h - self.PAD_T - self.PAD_B
        y = lambda v: self.PAD_T + (top - v) / (top - bottom) * plot_h

        v = bottom
        while v <= top + step / 2:
            self.create_line(self.PAD_L, y(v), w - self.PAD_R, y(v), fill=BORDER if v else AXIS)
            self.create_text(self.PAD_L - 10, y(v), text=format_isk(v), anchor="e", fill=MUTED,
                             font=("TkDefaultFont", 9))
            v += step

        slot = (w - self.PAD_L - self.PAD_R) / len(self.sessions)
        bar_w = max(3, min(28, slot - 2))
        label_every = max(1, int(70 // slot) + 1)
        last = len(self.sessions) - 1
        for i, s in enumerate(self.sessions):
            cx = self.PAD_L + slot * (i + 0.5)
            x0, x1 = cx - bar_w / 2, cx + bar_w / 2
            self._bar(x0, x1, y(0), y(s.profit), KIND_COLOR[s.kind])
            self.bars.append((self.PAD_L + slot * i, self.PAD_L + slot * (i + 1), s, cx, y(s.profit)))
            if (i % label_every == 0 and last - i >= label_every) or i == last:
                self.create_text(cx, h - self.PAD_B + 14, text=f"{s.started_at:%d %b}", fill=MUTED,
                                 font=("TkDefaultFont", 9))

    def _bar(self, x0, x1, base, end, color):
        """Bar anchored to the baseline with a rounded data end."""
        if abs(base - end) < 1:
            self.create_line(x0, base, x1, base, fill=color, width=2)
            return
        r = min(4, (x1 - x0) / 2, abs(base - end))
        up = end < base
        if up:
            self.create_rectangle(x0, end + r, x1, base, fill=color, width=0)
            self.create_rectangle(x0 + r, end, x1 - r, end + r, fill=color, width=0)
            self.create_oval(x0, end, x0 + 2 * r, end + 2 * r, fill=color, width=0)
            self.create_oval(x1 - 2 * r, end, x1, end + 2 * r, fill=color, width=0)
        else:
            self.create_rectangle(x0, base, x1, end - r, fill=color, width=0)
            self.create_rectangle(x0 + r, end - r, x1 - r, end, fill=color, width=0)
            self.create_oval(x0, end - 2 * r, x0 + 2 * r, end, fill=color, width=0)
            self.create_oval(x1 - 2 * r, end - 2 * r, x1, end, fill=color, width=0)

    def _hover(self, event):
        self.delete("tip")
        for x0, x1, s, cx, top in self.bars:
            if x0 <= event.x < x1:
                break
        else:
            return
        lines = [
            f"{KIND_NAME[s.kind]} · {s.started_at:%a %d %b %Y, %H:%M}",
            f"Profit  {signed_isk(s.profit)}",
            f"{s.runs} {'runs' if s.kind == ABYSS else 'sites'} · {format_minutes(s.minutes)}",
            f"ISK/hr  {format_isk(s.isk_per_hour)}",
        ]
        self.create_line(cx, self.PAD_T, cx, self.winfo_height() - self.PAD_B, fill=AXIS, dash=(2, 3), tags="tip")
        text = self.create_text(0, 0, text="\n".join(lines), anchor="nw", fill=INK,
                                font=("TkDefaultFont", 10), tags="tip")
        bx0, by0, bx1, by1 = self.bbox(text)
        tw, th = bx1 - bx0 + 20, by1 - by0 + 16
        tx = cx + 12 if cx + 12 + tw < self.winfo_width() else cx - 12 - tw
        ty = min(max(self.PAD_T, event.y - th / 2), self.winfo_height() - th - 4)
        box = self.create_rectangle(tx, ty, tx + tw, ty + th, fill=RAISED, outline=AXIS, tags="tip")
        self.create_rectangle(tx + 10, ty + 11, tx + 18, ty + 19, fill=KIND_COLOR[s.kind], width=0, tags="tip")
        self.coords(text, tx + 24, ty + 8)
        self.tag_raise(text, box)


def _nice_step(span, ticks=4):
    raw = span / ticks
    magnitude = 10 ** len(str(int(raw))) / 10 if raw >= 1 else 1
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * magnitude:
            return mult * magnitude
    return 10 * magnitude


class HistoryPage(ctk.CTkFrame):
    """Lifetime stats, a profit chart and the list of past sessions."""

    FILTERS = {"All": None, "Abyss": ABYSS, "Incursion": INCURSION}

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.tracker = app.tracker

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text="History", font=font(26, "bold"), text_color=INK).pack(side="left")
        ctk.CTkButton(
            header, text="Import Sessions.txt", width=160, fg_color="transparent", border_width=1,
            border_color=AXIS, hover_color=BORDER, text_color=INK, command=self.import_txt,
        ).pack(side="right")
        self.filter = ctk.CTkSegmentedButton(header, values=list(self.FILTERS), command=lambda _v: self.refresh())
        self.filter.set("All")
        self.filter.pack(side="right", padx=12)

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x")
        self.cards = {}
        for i, (key, label) in enumerate([("profit", "Total profit"), ("rate", "ISK / hour"),
                                          ("runs", "Runs & sites"), ("time", "Time"), ("sessions", "Sessions")]):
            cards.grid_columnconfigure(i, weight=1, uniform="cards")
            self.cards[key] = StatCard(cards, label)
            self.cards[key].grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))

        chart_card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=10, border_width=1, border_color=BORDER)
        chart_card.pack(fill="x", pady=12)
        top = ctk.CTkFrame(chart_card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(top, text="PROFIT PER SESSION", font=font(11, "bold"), text_color=MUTED).pack(side="left")
        self.legend = ctk.CTkFrame(top, fg_color="transparent")
        self.legend.pack(side="right")
        for kind in (ABYSS, INCURSION):
            ctk.CTkFrame(self.legend, width=10, height=10, corner_radius=2, fg_color=KIND_COLOR[kind]).pack(
                side="left", padx=(12, 6)
            )
            ctk.CTkLabel(self.legend, text=KIND_NAME[kind], font=font(12), text_color=INK_2).pack(side="left")
        self.chart = ProfitChart(chart_card)
        self.chart.pack(fill="x", padx=12, pady=(0, 12))

        self.table = RunLog(
            self,
            [("Date", 170, "w"), ("Type", 130, "w"), ("Runs", 60, "e"), ("Time", 0, "e"),
             ("Profit", 120, "e"), ("ISK / hr", 120, "e")],
            self.delete_session,
        )
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        kind = self.FILTERS[self.filter.get()]
        totals = self.tracker.totals(kind)
        self.cards["profit"].set(signed_isk(totals.profit), profit_color(totals.profit))
        self.cards["rate"].set(format_isk(totals.isk_per_hour))
        self.cards["runs"].set(str(totals.runs))
        self.cards["time"].set(format_minutes(totals.minutes))
        self.cards["sessions"].set(str(totals.sessions))

        sessions = [s for s in self.tracker.sessions(kind) if s.runs]
        if kind:
            self.legend.pack_forget()
        else:
            self.legend.pack(side="right")
        self.chart.show(sessions)
        rows = []
        for s in sessions[:300]:
            kind_label = KIND_NAME[s.kind] + (" · live" if s.active else " · txt" if s.imported else "")
            rows.append((s.id, [
                (f"{s.started_at:%d %b %Y  %H:%M}", INK_2),
                (kind_label, GOOD_TEXT if s.active else INK_2),
                (str(s.runs), INK_2),
                (format_minutes(s.minutes), INK_2),
                (signed_isk(s.profit), profit_color(s.profit)),
                (format_isk(s.isk_per_hour), INK),
            ]))
        self.table.show(rows, "No sessions yet. Finished sessions show up here.")

    def delete_session(self, session_id):
        s = self.tracker.session(session_id)
        if s and messagebox.askyesno(
            "Delete session",
            f"Delete the {KIND_NAME[s.kind].lower()} session from {s.started_at:%d %b %Y}?\n\n"
            f"{s.runs} runs · {signed_isk(s.profit)} ISK. This can't be undone.",
            parent=self,
        ):
            self.tracker.delete_session(session_id)
            self.app.refresh()

    def import_txt(self):
        path = filedialog.askopenfilename(
            parent=self, title="Import Sessions.txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            count = self.tracker.import_sessions_txt(path)
        except OSError as err:
            messagebox.showerror("Import failed", str(err), parent=self)
            return
        messagebox.showinfo("Import", f"Imported {count} session{'s' if count != 1 else ''}.", parent=self)
        self.app.refresh()


class App(ctk.CTk):
    def __init__(self, tracker=None):
        super().__init__(fg_color=PAGE)
        self.tracker = tracker or Tracker()
        self.title("Abyss Tracker")
        self.geometry("1180x780")
        self.minsize(1000, 680)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, width=220)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.pack_propagate(False)
        ctk.CTkLabel(sidebar, text="ABYSS TRACKER", font=font(18, "bold"), text_color=INK).pack(
            anchor="w", padx=22, pady=(26, 0)
        )
        ctk.CTkLabel(sidebar, text="EVE profit manager", font=font(12), text_color=MUTED).pack(anchor="w", padx=22)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self.pages = {
            "abyss": AbyssPage(content, self),
            "incursion": IncursionPage(content, self),
            "history": HistoryPage(content, self),
        }
        self.nav = {}
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=12, pady=(28, 0))
        for i, (key, label) in enumerate([("abyss", "Abyss"), ("incursion", "Incursion"), ("history", "History")]):
            btn = ctk.CTkButton(
                nav_frame, text=label, anchor="w", height=40, font=font(14), corner_radius=8,
                fg_color="transparent", hover_color=RAISED, text_color=INK_2,
                command=lambda k=key: self.show(k),
            )
            btn.pack(fill="x", pady=2)
            self.nav[key] = btn
            self.bind(f"<Control-Key-{i + 1}>", lambda _e, k=key: self.show(k))

        lifetime = ctk.CTkFrame(sidebar, fg_color="transparent")
        lifetime.pack(side="bottom", fill="x", padx=22, pady=24)
        ctk.CTkLabel(lifetime, text="LIFETIME", font=font(11, "bold"), text_color=MUTED).pack(anchor="w")
        self.lifetime_profit = ctk.CTkLabel(lifetime, text="", font=font(20, "bold"), text_color=INK)
        self.lifetime_profit.pack(anchor="w")
        self.lifetime_rate = ctk.CTkLabel(lifetime, text="", font=font(12), text_color=INK_2)
        self.lifetime_rate.pack(anchor="w")

        self.current = None
        for page in ("abyss", "incursion"):
            self.pages[page].resume()
        self.refresh()
        active = next((k for k in ("abyss", "incursion") if self.pages[k].session_id), "abyss")
        self.show(active)

    def show(self, key):
        if self.current:
            self.pages[self.current].pack_forget()
        self.current = key
        self.pages[key].pack(fill="both", expand=True)
        for name, btn in self.nav.items():
            live = name in ("abyss", "incursion") and self.pages[name].session_id
            label = btn.cget("text").removesuffix("  ●")
            btn.configure(
                text=label + ("  ●" if live else ""),
                fg_color=RAISED if name == key else "transparent",
                text_color=INK if name == key else INK_2,
            )

    def refresh(self):
        for page in self.pages.values():
            page.refresh()
        totals = self.tracker.totals()
        self.lifetime_profit.configure(text=signed_isk(totals.profit), text_color=profit_color(totals.profit))
        self.lifetime_rate.configure(
            text=f"{format_isk(totals.isk_per_hour)}/hr · {format_minutes(totals.minutes)}"
        )
        if self.current:
            self.show(self.current)


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    App().mainloop()


if __name__ == "__main__":
    main()
