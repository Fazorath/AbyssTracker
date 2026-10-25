"""
Desktop UI for the Abyss and Incursion tracker.

Run with:  python gui.py
"""
import math
import sqlite3
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

import customtkinter as ctk

from core import (
    ABYSS,
    INCURSION,
    MAXTIME,
    TIERS,
    WEATHERS,
    Tracker,
    best_weather,
    format_isk,
    format_minutes,
    isk_per_hour,
    tier_label,
)
from clock import read_clock
from journal import get_incursion_payouts
from location import AbyssWatcher, get_location
from loot import get_assets, get_prices, value_change
from wallet import get_wallet
from account import SIGN_IN_ERRORS, Account
from theme import NEUTRAL_THEME, asset_path, load_fonts, theme_for, ui_family

# Text colours shared by every theme
INK = "#f0efec"
INK_2 = "#c3c2b7"
WARNING = "#fab219"
GOOD_TEXT = "#3fcf5e"
CRITICAL_TEXT = "#ec6b6b"

KIND_COLOR = {ABYSS: "#d95926", INCURSION: "#3987e5"}
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
        value = float(raw) * (scale or 1.0)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise ValueError(f"Enter a number for {field} (e.g. 31.5, 1.2b, 800k)")
    return value


def parse_minutes(text, field="time"):
    """Parse minutes, also accepting 'mm:ss'."""
    raw = text.strip()
    try:
        if ":" in raw:
            mins, secs = raw.split(":", 1)
            value = int(mins) + int(secs) / 60
        else:
            value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise ValueError(f"Enter minutes for {field} (e.g. 14.5 or 14:30)")
    return value


def signed_isk(millions):
    return ("+" if millions > 0 else "") + format_isk(millions)


def profit_color(millions):
    return GOOD_TEXT if millions > 0 else CRITICAL_TEXT if millions < 0 else INK_2


# Font family of every widget and canvas; App.use_ui_font() sets it once Tk is up
UI_FAMILY = "TkDefaultFont"


def font(size=13, weight="normal"):
    return ctk.CTkFont(size=size, weight=weight)


def canvas_font(size, weight="normal"):
    """Font for tk.Canvas text, in the same family as the CTk widgets."""
    return (UI_FAMILY, size, weight)


def mix(color, other, amount):
    """Blend two '#rrggbb' colours: amount 0 gives color, 1 gives other."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def accent_hover(theme):
    """Hover colour for accent-filled buttons."""
    return mix(theme.accent, theme.bg, 0.2)


# paint() options for accent-filled buttons
PRIMARY = {"fg_color": "accent", "hover_color": accent_hover, "text_color": "bg"}


URGENCY_COLOR = {"warning": WARNING, "critical": CRITICAL_TEXT}
TOGGLE_TEXT = {"ready": "Start timer", "paused": "Resume", "expired": "Resume"}  # a running timer offers Pause


def digit_color(face, theme):
    """Colour of a timer's digits: the accent, or a warning as the countdown runs out."""
    return URGENCY_COLOR.get(face.urgency, theme.accent)


class FixedDigits:
    """
    Bold text drawn on a canvas one item per character, each digit in a
    fixed-width cell, so proportional digits don't shift as they change.
    """

    def __init__(self, canvas, size, align="center"):
        self.canvas = canvas
        self.align = align  # the x given to place() is the text's centre, or its left edge for "left"
        self.font = tkfont.Font(canvas, family=UI_FAMILY, size=size, weight="bold")
        self.digit_width = max(self.font.measure(d) for d in "0123456789")
        self.items = []
        self.at = (0, 0)

    def show(self, text, color):
        while len(self.items) < len(text):
            self.items.append(self.canvas.create_text(0, 0, font=self.font))
        while len(self.items) > len(text):
            self.canvas.delete(self.items.pop())
        for item, char in zip(self.items, text):
            self.canvas.itemconfigure(item, text=char, fill=color)
        self.place(*self.at)

    def place(self, x, y):
        self.at = (x, y)
        chars = [self.canvas.itemcget(item, "text") for item in self.items]
        widths = [self.digit_width if c.isdigit() else self.font.measure(c) for c in chars]
        x = x if self.align == "left" else x - sum(widths) / 2
        for item, width in zip(self.items, widths):
            self.canvas.coords(item, x + width / 2, y)
            x += width


class TimerPanel(tk.Canvas):
    """
    A countdown (for the abyssal timer) or a stopwatch (for incursion sites), drawn
    large and centred over concentric rings.

    When the time field is left blank, the page uses this timer's value.
    """

    RINGS = ((0.98, None), (0.76, (4, 10)), (0.54, None))  # (radius as a share of the height, dash)

    def __init__(self, master, countdown_minutes=None):
        super().__init__(master, highlightthickness=0, height=360)
        self.countdown = countdown_minutes * 60 if countdown_minutes else None
        self.elapsed_before = 0.0
        self.started = None
        self._job = None
        self.theme = NEUTRAL_THEME

        self.rings = [self.create_oval(0, 0, 0, 0, width=1, dash=dash or ()) for _, dash in self.RINGS]
        self.caption = self.create_text(0, 0, text="", font=canvas_font(-14))
        self.display = FixedDigits(self, -132)
        self.hint = self.create_text(0, 0, text="", font=canvas_font(-15))
        self.buttons = ctk.CTkFrame(self)
        self.toggle_btn = ctk.CTkButton(self.buttons, text="Start", width=140, height=46, font=font(16, "bold"),
                                        command=self.toggle)
        self.toggle_btn.pack(side="left", padx=5)
        self.reset_btn = ctk.CTkButton(self.buttons, text="Reset", width=96, height=46, font=font(16),
                                       fg_color="transparent", border_width=1, text_color=INK, command=self.reset)
        self.reset_btn.pack(side="left", padx=5)
        self.button_window = self.create_window(0, 0, window=self.buttons)
        self.bind("<Configure>", lambda _e: self._layout())
        self.set_theme(NEUTRAL_THEME)

    @property
    def running(self):
        return self.started is not None

    def elapsed(self):
        return self.elapsed_before + (time.monotonic() - self.started if self.running else 0)

    def value_minutes(self):
        """Minutes left (countdown) or elapsed (stopwatch); None if the timer was never started."""
        if not self.running and self.elapsed_before <= 0:  # not by elapsed(): a coarse clock reads 0 just after Start
            return None
        elapsed = self.elapsed()
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

    def set_caption(self, text):
        self.itemconfigure(self.caption, text=text)

    def set_theme(self, theme):
        self.theme = theme
        self.configure(bg=theme.bg)
        for ring in self.rings:
            self.itemconfigure(ring, outline=mix(theme.line, theme.bg, 0.5))
        self.itemconfigure(self.caption, fill=theme.soft)
        self.itemconfigure(self.hint, fill=theme.soft)
        self.buttons.configure(fg_color=theme.bg)
        self.toggle_btn.configure(fg_color=theme.accent, hover_color=accent_hover(theme), text_color=theme.bg)
        self.reset_btn.configure(border_color=theme.line, hover_color=theme.panel)
        self._render()

    def _layout(self):
        w, h = self.winfo_width(), self.winfo_height()
        cx, cy = w / 2, h / 2
        for ring, (share, _) in zip(self.rings, self.RINGS):
            r = share * h
            self.coords(ring, cx - r, cy - r, cx + r, cy + r)
        self.coords(self.caption, cx, cy - 100)
        self.display.place(cx, cy - 18)
        self.coords(self.hint, cx, cy + 62)
        self.coords(self.button_window, cx, cy + 122)

    def _tick(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        if self.running:
            self._render()
            self._job = self.after(250, self._tick)

    def face(self):
        return read_clock(self.countdown, self.elapsed(), self.running)

    def toggle_text(self, face):
        # A countdown past zero keeps running, so it still offers to pause
        return "Pause timer" if self.running else TOGGLE_TEXT[face.state]

    def _render(self):
        face = self.face()
        self.display.show(face.text, digit_color(face, self.theme))
        if face.state == "expired":
            hint = "Timer expired"
        elif self.theme.hint:
            hint = self.theme.hint
        elif face.state != "ready":
            hint = "Leave the time field blank to use this"
        else:
            hint = "Start when you enter" if self.countdown else "Start when the site starts"
        self.itemconfigure(self.hint, text=hint)
        self.toggle_btn.configure(text=self.toggle_text(face))


class RunTile(ctk.CTkFrame):
    """A logged run or site: profit, duration and ISK/hour, with edit and delete buttons."""

    def __init__(self, master, theme, title, run, on_edit, on_delete):
        super().__init__(master, fg_color=theme.panel, corner_radius=10)
        color = profit_color(run.profit)
        ctk.CTkFrame(self, fg_color=color, height=3, corner_radius=0).pack(fill="x", padx=10)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=(14, 6), pady=(6, 0))
        ctk.CTkLabel(top, text=f"{title} · {format_minutes(run.minutes)}", font=font(12), text_color=theme.soft,
                     height=18).pack(side="left")
        for text, action in (("×", on_delete), ("✎", on_edit)):
            ctk.CTkButton(
                top, text=text, width=22, height=20, fg_color="transparent", hover_color=theme.line,
                text_color=theme.soft, command=lambda a=action: a(run.id),
            ).pack(side="right")
        ctk.CTkLabel(self, text=signed_isk(run.profit), font=font(24, "bold"), text_color=color, height=30).pack(
            anchor="w", padx=14
        )
        ctk.CTkLabel(self, text=f"{format_isk(isk_per_hour(run.profit, run.minutes))}/hr", font=font(12),
                     text_color=theme.soft, height=18).pack(anchor="w", padx=14, pady=(0, 10))


class FooterStat(ctk.CTkFrame):
    """A label and a number in the session footer."""

    def __init__(self, master, label, paint):
        super().__init__(master, fg_color="transparent")
        paint(ctk.CTkLabel(self, text=label, font=font(14)), text_color="soft").pack(side="left")
        self.value = ctk.CTkLabel(self, text="—", font=font(18, "bold"), text_color=INK)
        self.value.pack(side="left", padx=(8, 0))
        self.sub = paint(ctk.CTkLabel(self, text="", font=font(12)), text_color="soft")
        self.sub.pack(side="left", padx=(6, 0))

    def set(self, value, color=INK, sub=""):
        self.value.configure(text=value, text_color=color)
        self.sub.configure(text=sub)


class ChipGroup(ctk.CTkFrame):
    """A row of round buttons where one is picked, like a radio group."""

    def __init__(self, master, values, value, command):
        super().__init__(master, fg_color="transparent")
        self.value = value
        self.command = command
        self.theme = NEUTRAL_THEME
        self.chips = {}
        for v in values:
            self.chips[v] = ctk.CTkButton(
                self, text=v, width=0, height=34, corner_radius=17, border_width=1, font=font(13, "bold"),
                command=lambda v=v: self.pick(v),
            )
            self.chips[v].pack(side="left", padx=(0, 6))

    def get(self):
        return self.value

    def pick(self, value):
        self.value = value
        self.set_theme(self.theme)
        self.command(value)

    def set_theme(self, theme):
        self.theme = theme
        for v, chip in self.chips.items():
            on = v == self.value
            chip.configure(
                fg_color=theme.accent if on else "transparent", border_color=theme.accent if on else theme.line,
                hover_color=accent_hover(theme) if on else theme.line, text_color=theme.bg if on else INK,
            )


class EditRunDialog(ctk.CTkToplevel):
    """
    Modal form for correcting a logged run or site.

    on_save gets the typed values and returns the updated run, or raises
    ValueError to keep the dialog open with the message shown.
    """

    def __init__(self, master, title, fields, theme, on_save):
        super().__init__(master, fg_color=theme.panel)
        self.title(title)
        self.resizable(False, False)
        self.on_save = on_save
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(padx=24, pady=(20, 0), anchor="w")
        self.entries = []
        for column, (label, value) in enumerate(fields):
            ctk.CTkLabel(form, text=label, font=font(12), text_color=theme.soft).grid(
                row=0, column=column, sticky="w", padx=(0, 12)
            )
            entry = ctk.CTkEntry(form, width=170, height=36, font=font(15), fg_color=theme.bg,
                                 border_color=theme.line)
            entry.insert(0, value)
            entry.grid(row=1, column=column, sticky="w", padx=(0, 12), pady=(2, 0))
            entry.bind("<Return>", lambda _e: self.save())
            entry.bind("<Escape>", lambda _e: self.destroy())
            self.entries.append(entry)
        self.message = ctk.CTkLabel(self, text="", text_color=CRITICAL_TEXT, font=font(12), height=16)
        self.message.pack(anchor="w", padx=24, pady=(8, 0))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(anchor="w", padx=24, pady=(4, 20))
        ctk.CTkButton(
            buttons, text="Save", width=110, height=36, font=font(14, "bold"),
            fg_color=theme.accent, hover_color=accent_hover(theme), text_color=theme.bg, command=self.save,
        ).pack(side="left")
        ctk.CTkButton(
            buttons, text="Cancel", width=90, height=36, fg_color="transparent", border_width=1,
            border_color=theme.line, hover_color=theme.line, text_color=INK, command=self.destroy,
        ).pack(side="left", padx=8)
        self.transient(master.winfo_toplevel())
        self.after(50, self._focus)

    def _focus(self):
        self.grab_set()
        self.entries[0].focus_set()
        self.entries[0].select_range(0, "end")

    def save(self):
        try:
            self.on_save(*(entry.get() for entry in self.entries))
        except ValueError as err:
            self.message.configure(text=str(err))
            return
        self.destroy()


class Painter:
    """Mixin for a window part whose widgets recolour with the Filament theme; set self.painters = []."""

    def paint(self, widget, **options):
        """
        Recolour a widget whenever the theme changes.

        Args:
            widget: The widget to colour.
            **options: configure() options, each a Theme field name or a function of the theme.

        Returns:
            The widget.
        """
        self.painters.append(lambda t: widget.configure(
            **{k: v(t) if callable(v) else getattr(t, v) for k, v in options.items()}
        ))
        return widget

    def repaint(self, theme):
        for painter in self.painters:
            painter(theme)


def logged_text(run):
    return f"Logged {signed_isk(run.profit)} in {format_minutes(run.minutes)}"


def set_entry(entry, text):
    """Replace an entry's text. Skips needless edits, which would hide a CTkEntry's placeholder."""
    if entry.get() != text:
        entry.delete(0, "end")
        if text:
            entry.insert(0, text)


def style_tab(button, label, on, live, theme):
    """Colour a tab button for the selected or unselected state; a dot marks a live session."""
    button.configure(
        text=label + ("  ●" if live else ""),
        fg_color=theme.accent if on else "transparent", hover_color=accent_hover(theme) if on else theme.line,
        text_color=theme.bg if on else theme.soft,
    )


class EsiPoller:
    """
    A toolbar switch that, while on and a session is live, reads ESI off the UI
    thread every `poll_ms` and hands each result to `on_result`.
    """

    def __init__(self, page, text, read, on_result, label, poll_ms, retry_ms, on_start=None):
        self.page = page
        self.read = read  # client -> result, run off the UI thread
        self.on_result = on_result
        self.label = label  # names the read in error messages
        self.poll_ms, self.retry_ms = poll_ms, retry_ms
        self.on_start = on_start
        self._job = None
        self._reading = False
        self.switch = page.paint(
            ctk.CTkSwitch(page.toolbar, text=text, font=font(13), command=self.toggle),
            text_color="soft", progress_color="accent",
        )
        self.switch.pack(side="left", padx=(0, 12), before=page.toolbar.winfo_children()[0])

    def toggle(self):
        """Start or stop polling as the switch says."""
        if self._job:
            self.page.after_cancel(self._job)
            self._job = None
        if not self.switch.get():
            return
        client, problem = self.page.signed_in_client()
        if client is None:
            self.switch.deselect()
            self.page.flash(problem, CRITICAL_TEXT)
            return
        if self.on_start:
            self.on_start()
        self.poll()

    def poll(self):
        """Read off the UI thread, then schedule the next read."""
        self._job = None
        if not self.switch.get():
            return
        if self.page.session_id is not None and not self._reading:
            client, _ = self.page.signed_in_client()
            if client is not None:
                self._reading = True

                def done(result, error):
                    self._reading = False
                    if not self.switch.get():  # switched off while the read was out
                        return
                    if error is not None:
                        self.page.flash(f"{self.label}: {error}", CRITICAL_TEXT)
                        if self._job:  # back off rather than repeat the error every poll
                            self.page.after_cancel(self._job)
                            self._job = self.page.after(self.retry_ms, self.poll)
                    else:
                        self.on_result(result)

                self.page.app.run_async(lambda: self.read(client), done)
        self._job = self.page.after(self.poll_ms, self.poll)


class SessionPage(Painter, ctk.CTkFrame):
    """
    Shared layout for the Abyss and Incursion pages: a start screen and a live session
    screen, coloured by the session's Filament theme.
    """

    kind = None
    subtitle = ""
    unit = "run"
    pocket_label = ""  # label of the pocket overlay's one field

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.tracker = app.tracker
        self.session_id = None
        self._message_job = None
        self.theme = None
        self.painters = []  # functions that recolour a widget for a theme

        # Shown on the right of the app header while this page is open
        self.toolbar = ctk.CTkFrame(app.header, fg_color="transparent")
        badge = self.paint(ctk.CTkFrame(self.toolbar, corner_radius=6), fg_color="panel")
        badge.pack(side="left")
        self.filament = ctk.CTkLabel(badge, text="", font=font(13), text_color=INK, height=30)
        self.filament.pack(side="left", padx=(12, 0))
        self.status = ctk.CTkLabel(badge, text="", font=font(13), height=30)
        self.status.pack(side="left", padx=12)
        self.end_btn = self.paint(
            ctk.CTkButton(self.toolbar, text="End session", width=120, height=34, fg_color="transparent",
                          border_width=1, text_color=INK, command=self.end_session),
            border_color="line", hover_color="panel",
        )

        # Start screen
        self.start_view = self.paint(ctk.CTkFrame(self, corner_radius=12, border_width=1),
                                     fg_color="panel", border_color="line")
        inner = ctk.CTkFrame(self.start_view, fg_color="transparent")
        inner.pack(padx=40, pady=40, anchor="w")
        ctk.CTkLabel(inner, text="Start a session", font=font(20, "bold"), text_color=INK).pack(anchor="w")
        self.paint(ctk.CTkLabel(inner, text=self.subtitle, font=font(13), justify="left", wraplength=560),
                   text_color="soft").pack(anchor="w", pady=(4, 20))
        self.start_form = ctk.CTkFrame(inner, fg_color="transparent")
        self.start_form.pack(anchor="w")
        self.build_start_form(self.start_form)
        self.paint(
            ctk.CTkButton(inner, text="Start session", height=40, width=180, font=font(14, "bold"),
                          command=self.start_session),
            **PRIMARY,
        ).pack(anchor="w", pady=(20, 0))
        self.start_message = ctk.CTkLabel(inner, text="", text_color=CRITICAL_TEXT, font=font(12))
        self.start_message.pack(anchor="w", pady=(8, 0))

        # Live session screen: countdown, run tiles beside the log form, then the session stats
        self.live_view = ctk.CTkFrame(self, fg_color="transparent")
        self.timer = self.build_timer(self.live_view)
        self.timer.pack(fill="both", expand=True)

        runs = ctk.CTkFrame(self.live_view, fg_color="transparent")
        runs.pack(fill="x", pady=(12, 0))
        runs.grid_columnconfigure(0, weight=1)
        self.tiles = self.paint(
            ctk.CTkScrollableFrame(runs, orientation="horizontal", height=92),
            fg_color="bg", scrollbar_button_color="line", scrollbar_button_hover_color="soft",
        )
        self.tiles.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.empty = self.paint(ctk.CTkLabel(self.tiles, text="", font=font(13)), text_color="soft")

        form_card = self.paint(ctk.CTkFrame(runs, corner_radius=10), fg_color="panel")
        form_card.grid(row=0, column=1, sticky="nsew")
        self.log_form = ctk.CTkFrame(form_card, fg_color="transparent")
        self.log_form.pack(anchor="w", padx=14, pady=(12, 0))
        self.build_log_form(self.log_form)
        self.paint(
            ctk.CTkButton(self.log_form, text=f"Log {self.unit}  ⏎", height=36, width=120, font=font(14, "bold"),
                          command=self.log),
            **PRIMARY,
        ).grid(row=1, column=len(self.entries()), sticky="w", pady=(2, 0))
        self.message = ctk.CTkLabel(form_card, text="", font=font(12), height=18)
        self.message.pack(anchor="w", padx=14, pady=(4, 8))

        footer = ctk.CTkFrame(self.live_view, fg_color="transparent")
        footer.pack(fill="x", pady=(14, 0))
        self.stats = {}
        for key, label in self.stat_labels():
            self.stats[key] = FooterStat(footer, label, self.paint)
            self.stats[key].pack(side="left", padx=(0, 32))
        self.lifetime = self.paint(ctk.CTkLabel(footer, text="", font=font(14)), text_color="soft")
        self.lifetime.pack(side="right")

        for entry in self.entries():
            entry.bind("<Return>", lambda _e: self.log())
        self.set_theme(self.idle_theme())

    # --- hooks for subclasses ---------------------------------------------

    def build_start_form(self, frame): ...
    def build_log_form(self, frame): ...
    def build_timer(self, master): ...
    def entries(self): return []
    def stat_labels(self): return []
    def start_args(self): return {}
    def log_run(self): ...
    def end_note(self): return ""
    def update_stats(self, session, runs): ...
    def timer_caption(self, session): return ""
    def lifetime_totals(self, session): return "", None
    def idle_theme(self): return theme_for(self.kind, None)
    def after_log(self): ...
    def edit_fields(self, run): return []
    def save_edit(self, run, *values): ...
    def pocket_fields(self): return None, None  # (entry the overlay's field fills, time entry it leaves blank)

    # --- shared behaviour -------------------------------------------------

    def set_theme(self, theme):
        """Recolour the page, and the app around it when the page is showing."""
        if theme == self.theme:
            return
        self.theme = theme
        self.repaint(theme)
        self.timer.set_theme(theme)
        if self.winfo_manager():
            self.app.apply_theme(theme)

    def field(self, frame, column, label, width=170, placeholder=""):
        """Add a labelled entry to a form row and return the entry."""
        self.paint(ctk.CTkLabel(frame, text=label, font=font(12)), text_color="soft").grid(
            row=0, column=column, sticky="w", padx=(0, 12)
        )
        entry = self.paint(
            ctk.CTkEntry(frame, width=width, height=36, font=font(15), placeholder_text=placeholder),
            fg_color="bg", border_color="line",
        )
        entry.grid(row=1, column=column, sticky="w", padx=(0, 12), pady=(2, 0))
        return entry

    def choice(self, frame, column, label, values, value, width=170):
        """Add a labelled dropdown to a form row and return it."""
        self.paint(ctk.CTkLabel(frame, text=label, font=font(12)), text_color="soft").grid(
            row=0, column=column, sticky="w", padx=(0, 12)
        )
        menu = self.paint(
            ctk.CTkOptionMenu(frame, values=values, width=width, height=36, font=font(15), text_color=INK),
            fg_color="bg", button_color="line", button_hover_color="panel",
            dropdown_fg_color="panel", dropdown_hover_color="line",
        )
        menu.set(value)
        menu.grid(row=1, column=column, sticky="w", padx=(0, 12), pady=(2, 0))
        return menu

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
            f"{session.runs} {self.unit}s · {signed_isk(session.profit)} ISK · {format_minutes(session.minutes)}"
            f"{self.end_note()}",
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
            run = self.submit()
        except ValueError as err:
            self.flash(str(err), CRITICAL_TEXT)
            return
        self.flash(logged_text(run), profit_color(run.profit))
        self.entries()[0].focus_set()

    def submit(self):
        """Log the run or site in the form and return it; raises ValueError for a bad value."""
        self.used_timer = False
        run = self.log_run()
        if self.used_timer:  # a typed time leaves a running timer alone
            self.timer.reset()
        self.after_log()
        self.app.refresh()
        return run

    def pocket_log(self, amount_text):
        """
        Log from the pocket overlay: its one field fills this page's and the time comes from the timer.

        Returns the run, or raises ValueError and leaves this page's form as it was.
        """
        if self.timer.value_minutes() is None:
            raise ValueError("Start the timer first, or expand to type the time.")
        amount, minutes = self.pocket_fields()
        typed = amount.get(), minutes.get()
        set_entry(amount, amount_text)
        set_entry(minutes, "")
        try:
            return self.submit()
        except ValueError:
            set_entry(amount, typed[0])
            set_entry(minutes, typed[1])
            raise

    def timer_or(self, entry, field):
        """Value typed in a time entry, or the timer's value when the entry is blank."""
        if entry.get().strip():
            return parse_minutes(entry.get(), field)
        value = self.timer.value_minutes()
        if value is None:
            raise ValueError(f"Enter {field}, or use the timer")
        self.used_timer = True
        return value

    def edit_run(self, run_id):
        run = self.tracker.run(run_id)
        if run is None:
            return

        def save(*values):
            edited = self.save_edit(run, *values)
            self.flash(
                f"Updated to {signed_isk(edited.profit)} in {format_minutes(edited.minutes)}",
                profit_color(edited.profit),
            )
            self.app.refresh()

        EditRunDialog(self, f"Edit {self.unit}", self.edit_fields(run), self.theme, save)

    def delete_run(self, run_id):
        run = self.tracker.run(run_id)
        if run and messagebox.askyesno(
            f"Delete {self.unit}",
            f"Delete this {self.unit}? ({signed_isk(run.profit)} ISK, {format_minutes(run.minutes)})",
            parent=self,
        ):
            self.tracker.delete_run(run_id)
            self.app.refresh()

    def signed_in_client(self):
        """The active character's ESI client and None, or None and why there isn't one."""
        try:
            client = self.app.account.client()
        except SIGN_IN_ERRORS as e:
            return None, str(e)
        return (client, None) if client else (None, "Sign in under Settings first.")

    def notify(self, text, color=None):
        self.flash(text, color)
        if self.app.pocket:
            self.app.pocket.say(text, color)

    def flash(self, text, color=None):
        self.message.configure(text=text, text_color=color or self.theme.soft)
        if self._message_job:
            self.after_cancel(self._message_job)
        self._message_job = self.after(5000, lambda: self.message.configure(text=""))

    def refresh(self):
        session = self.tracker.session(self.session_id) if self.session_id else None
        if session is None:
            self.session_id = None
            self.set_theme(self.idle_theme())
            self.live_view.pack_forget()
            self.end_btn.pack_forget()
            self.start_view.pack(expand=True)
            self.filament.configure(text="")
            self.status.configure(text="No active session", text_color=self.theme.soft)
            return
        self.set_theme(theme_for(session.kind, session.weather))
        self.start_view.pack_forget()
        self.live_view.pack(fill="both", expand=True)
        self.end_btn.pack(side="left", padx=(10, 0))
        self.filament.configure(text=f"{tier_label(session.tier)} {session.weather}  ·" if session.weather else "")
        self.status.configure(text=f"● Live {session.started_at:%H:%M}", text_color=GOOD_TEXT)
        runs = self.tracker.runs(self.session_id)
        self.timer.set_caption(self.timer_caption(session))
        self.update_stats(session, runs)
        label, totals = self.lifetime_totals(session)
        self.lifetime.configure(
            text=f"{label}: {signed_isk(totals.profit)} · {format_isk(totals.isk_per_hour)}/hr" if totals else ""
        )
        self.show_tiles(runs)

    def show_tiles(self, runs):
        """One tile per run, oldest first, scrolled so the newest is in view."""
        for child in self.tiles.winfo_children():
            if child is not self.empty:
                child.destroy()
        if not runs:
            self.empty.configure(text=f"No {self.unit}s yet. Log your first one here.")
            self.empty.pack(side="left", padx=8, pady=30)
            return
        self.empty.pack_forget()
        title = self.unit.capitalize()
        for i, run in enumerate(runs):
            RunTile(self.tiles, self.theme, f"{title} {i + 1}", run, self.edit_run, self.delete_run).pack(
                side="left", padx=(0, 10), fill="y"
            )
        # CTkScrollableFrame has no public scroll call; its canvas does
        self.after_idle(lambda: self.tiles._parent_canvas.xview_moveto(1.0))


class AbyssPage(SessionPage):
    kind = ABYSS
    subtitle = (
        "Enter your wallet and pick the filament before the first run. After each run, enter the new "
        "wallet total and the time left on the 20-minute timer, or run the built-in timer and leave the time blank."
    )
    unit = "run"
    pocket_label = "Wallet after run (M)"
    LOCATION_POLL_MS = 5000  # ESI caches the location for 5 s; the client never asks sooner
    LOCATION_RETRY_MS = 30000  # after a failed read
    LOOT_POLL_MS = 5 * 60 * 1000  # ESI caches assets for an hour; the client never asks sooner

    def __init__(self, master, app):
        super().__init__(master, app)
        self._watcher = AbyssWatcher()
        self._watched_session = None
        self.detect = EsiPoller(
            self, "Detect runs from EVE", lambda client: get_location(client, client.character.id),
            lambda location: self.see_abyss(location.in_abyss), "Location",
            self.LOCATION_POLL_MS, self.LOCATION_RETRY_MS, on_start=self.reset_watcher,
        ).switch
        self._valuing = False
        self._loot_problem = None  # an asset error or mismatch, shown instead of the loot's time
        self._loot_waiting = "reading assets..."  # shown before the session's first reading
        self._loot_poll()

    def _loot_poll(self):
        self.value_loot()
        self.after(self.LOOT_POLL_MS, self._loot_poll)

    def value_loot(self):
        """
        Read the assets off the UI thread: the first reading of a session is its
        baseline, and later ones value what changed since. Quiet when signed out.
        """
        if self.session_id is None or self._valuing:
            return
        client, _ = self.signed_in_client()
        if client is None:
            if self._loot_waiting != "sign in to value loot":
                self._loot_waiting = "sign in to value loot"
                self.refresh()
            return
        self._loot_waiting = "reading assets..."
        session_id = self.session_id
        has_baseline = self.tracker.loot_baseline(session_id) is not None
        self._valuing = True

        def read():
            return get_assets(client, client.character.id), get_prices(client) if has_baseline else None

        def done(result, error):
            self._valuing = False
            if session_id != self.session_id:  # the session changed while the read was out
                self.value_loot()
            elif error is not None:
                self.loot_failed(error)
            else:
                self.take_assets(*result)

        self.app.run_async(read, done)

    def take_assets(self, assets, prices):
        """Use an asset reading: the session's baseline if it has none, else value the change since."""
        baseline = self.tracker.loot_baseline(self.session_id)
        self._loot_problem = None
        if baseline is None:
            self.tracker.set_loot_baseline(self.session_id, assets.character_id, assets.quantities)
        elif baseline.character_id != assets.character_id:
            self._loot_problem = "baseline is for another character"
        elif prices is not None:
            self.tracker.set_loot(self.session_id, value_change(baseline.quantities, assets.quantities, prices),
                                  datetime.fromtimestamp(assets.fetched_at))
        self.refresh()

    def loot_failed(self, error):
        self._loot_problem = f"Assets: {error}"
        self.refresh()

    def start_session(self):
        self._loot_problem = None
        super().start_session()
        self.value_loot()

    def end_note(self):
        loot = self.tracker.loot(self.session_id)
        return f"\n\nUnsold loot: {signed_isk(loot.millions)} ISK at market prices." if loot else ""

    def resume(self):
        super().resume()
        self.value_loot()

    def build_start_form(self, frame):
        self.start_isk = self.field(frame, 0, "Wallet now (million ISK)", 220, "e.g. 1,250 or 1.25b")
        self.start_isk.bind("<Return>", lambda _e: self.start_session())
        self.start_wallet_note = self.wallet_fetch(frame, 2, self.start_isk)
        weather, tier = self.tracker.last_filament()
        self.tier_labels = [tier_label(t) for t in range(len(TIERS))]
        self.tier = self.choice(frame, 1, "Tier", self.tier_labels, self.tier_labels[tier or 0], 170)
        self.paint(ctk.CTkLabel(frame, text="Weather", font=font(12)), text_color="soft").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(16, 0)
        )
        self.weather = ChipGroup(frame, WEATHERS, weather or WEATHERS[0],
                                 lambda w: self.set_theme(theme_for(ABYSS, w)))
        self.weather.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.painters.append(self.weather.set_theme)

    def build_log_form(self, frame):
        self.after_isk = self.field(frame, 0, "Wallet after run (M)", 180, "e.g. 1,281")
        self.time_left = self.field(frame, 1, "Time left (min)", 120, "blank = timer")
        self.log_wallet_note = self.wallet_fetch(frame, 3, self.after_isk)

    def wallet_fetch(self, frame, column, entry):
        """Add a 'Fetch from EVE' button that fills the wallet entry; returns its status label."""
        note = self.paint(ctk.CTkLabel(frame, text="", font=font(11), justify="left", wraplength=190), text_color="soft")
        note.grid(row=0, column=column, sticky="w")
        self.paint(
            ctk.CTkButton(frame, text="Fetch from EVE", width=130, height=36, fg_color="transparent",
                          border_width=1, text_color=INK, command=lambda: self.fetch_wallet(entry, note)),
            border_color="line", hover_color="panel",
        ).grid(row=1, column=column, sticky="w", pady=(2, 0))
        return note

    def fetch_wallet(self, entry, note):
        """Read the wallet from ESI into `entry`. The balance is cached by ESI for about two minutes."""
        def show(text, color=None):
            note.configure(text=text, text_color=color or self.theme.soft)

        try:
            client = self.app.account.client()
        except SIGN_IN_ERRORS as e:
            show(str(e), CRITICAL_TEXT)
            return
        if client is None:
            show("Sign in under Settings first.", CRITICAL_TEXT)
            return
        show("Fetching...")

        def done(wallet, error):
            if error is not None:
                show(str(error), CRITICAL_TEXT)
                return
            entry.delete(0, "end")
            entry.insert(0, f"{wallet.millions:.2f}")
            stamp = time.strftime("%H:%M:%S", time.localtime(wallet.fetched_at))
            show(f"From EVE at {stamp}. ESI refreshes about every 2 min; edit to override.")

        self.app.run_async(lambda: get_wallet(client, client.character.id), done)

    def reset_watcher(self):
        """Detection switched on: the next reading is a fresh baseline."""
        self._watcher = AbyssWatcher()

    def see_abyss(self, in_abyss):
        """Act on a location reading: start the timer on entering, pause it and prompt to log on leaving."""
        if not self.detect.get() or self.session_id is None:
            return
        if self._watched_session != self.session_id:  # a new session starts from a fresh baseline
            self._watched_session = self.session_id
            self._watcher = AbyssWatcher()
        event = self._watcher.see(in_abyss)
        if event == "entered":
            self.timer.reset()
            self.timer.toggle()
            self.notify("Entered the abyss: timer started.")
        elif event == "left" and self.timer.value_minutes() is not None:
            if self.timer.running:
                self.timer.toggle()
            left = self.timer.face().text
            self.notify(f"Left the abyss with {left} left. Enter your wallet and log the run.", self.theme.accent)
            self.after_isk.focus_set()

    def build_timer(self, master):
        return TimerPanel(master, countdown_minutes=MAXTIME)

    def idle_theme(self):
        return theme_for(ABYSS, self.weather.get())

    def entries(self):
        return [self.after_isk, self.time_left]

    def pocket_fields(self):
        return self.after_isk, self.time_left

    def stat_labels(self):
        return [("profit", "Session"), ("loot", "Loot (unsold)"), ("rate", "ISK/hr"), ("time", "Time"),
                ("wallet", "Wallet")]

    def timer_caption(self, session):
        weather = (session.weather or "Abyssal").upper()
        return f"{weather} DEADSPACE  ·  RUN {session.runs + 1}  ·  TIME LEFT"

    def lifetime_totals(self, session):
        if session.weather:
            return f"{session.weather} lifetime", self.tracker.totals_by_weather().get(session.weather)
        return "Abyss lifetime", self.tracker.totals(ABYSS)

    def start_args(self):
        return {
            "starting_isk": parse_isk(self.start_isk.get(), "your wallet"),
            "weather": self.weather.get(),
            "tier": self.tier_labels.index(self.tier.get()),
        }

    def log_run(self):
        after = parse_isk(self.after_isk.get(), "wallet after")
        left = self.timer_or(self.time_left, "time left")
        before = self.tracker.current_isk(self.session_id)
        return self.tracker.log_abyss_run(self.session_id, before, after, left)

    def after_log(self):
        self.after_isk.delete(0, "end")
        self.time_left.delete(0, "end")
        self.value_loot()

    def edit_fields(self, run):
        return [("Wallet after run (M)", f"{run.isk_after:g}"), ("Time left (min)", f"{MAXTIME - run.minutes:g}")]

    def save_edit(self, run, isk_after, time_left):
        return self.tracker.edit_abyss_run(
            run.id, parse_isk(isk_after, "wallet after"), parse_minutes(time_left, "time left")
        )

    def update_stats(self, session, runs):
        avg = session.profit / session.runs if session.runs else 0
        self.stats["profit"].set(signed_isk(session.profit), profit_color(session.profit),
                                 f"avg {signed_isk(avg)} / run" if runs else "")
        self.stats["rate"].set(format_isk(session.isk_per_hour))
        self.stats["time"].set(format_minutes(session.minutes),
                               sub=f"{session.runs} runs" if runs else "")
        self.stats["wallet"].set(format_isk(self.tracker.current_isk(session.id) or 0),
                                 sub=f"from {format_isk(session.starting_isk or 0)}")
        loot = self.tracker.loot(session.id)
        if loot:
            unpriced = f" · {loot.unpriced} unpriced" if loot.unpriced else ""
            self.stats["loot"].set(signed_isk(loot.millions), profit_color(loot.millions),
                                   self._loot_problem or f"from EVE at {loot.as_of:%H:%M}{unpriced}")
        elif self.tracker.loot_baseline(session.id) is not None:
            self.stats["loot"].set(signed_isk(0), sub=self._loot_problem or "ESI updates assets hourly")
        else:
            self.stats["loot"].set("—", sub=self._loot_problem or self._loot_waiting)


class IncursionPage(SessionPage):
    kind = INCURSION
    subtitle = (
        "Set the payout per site; it's remembered for next time. Log each site with its time, "
        "or run the stopwatch and leave the time blank. Or switch on Log payouts from EVE to log each "
        "site from your wallet journal; ESI shows a payout up to an hour after the site."
    )
    unit = "site"
    pocket_label = "Payout (M)"
    JOURNAL_POLL_MS = 60000  # ESI caches the journal for an hour; the client asks again only once it expires
    JOURNAL_RETRY_MS = 300000  # after a failed read

    def __init__(self, master, app):
        super().__init__(master, app)
        self.auto_log = EsiPoller(
            self, "Log payouts from EVE", lambda client: get_incursion_payouts(client, client.character.id),
            self.take_payouts, "Journal", self.JOURNAL_POLL_MS, self.JOURNAL_RETRY_MS,
        ).switch

    def end_note(self):
        if not self.auto_log.get():
            return ""
        return "\n\nPayouts ESI hasn't shown yet (up to an hour after a site) won't be logged."

    def take_payouts(self, payouts):
        """Log a site for each payout not seen before and say so."""
        if not self.auto_log.get() or self.session_id is None:
            return
        sites = self.tracker.log_incursion_payouts(self.session_id, payouts)
        if not sites:
            return
        self.app.refresh()
        count = f"{len(sites)} site" + ("s" if len(sites) > 1 else "")
        total = sum(site.profit for site in sites)
        self.notify(f"Logged {count} from EVE: {signed_isk(total)} ISK", profit_color(total))

    def build_start_form(self, frame):
        self.per_site = self.field(frame, 0, "Payout per site (million ISK)", 240, "e.g. 31")
        saved = self.tracker.get_setting("incursion_payout")
        if saved:
            self.per_site.insert(0, saved)
        self.per_site.bind("<Return>", lambda _e: self.start_session())

    def build_log_form(self, frame):
        self.payout = self.field(frame, 0, "Payout (M)", 110)
        self.minutes = self.field(frame, 1, "Site time (min)", 150, "blank = stopwatch")

    def build_timer(self, master):
        return TimerPanel(master)

    def entries(self):
        return [self.minutes, self.payout]

    def pocket_fields(self):
        return self.payout, self.minutes

    def stat_labels(self):
        return [("profit", "Session"), ("rate", "ISK/hr"), ("time", "Time"), ("avg", "Avg site")]

    def timer_caption(self, session):
        return f"INCURSION  ·  SITE {session.runs + 1}  ·  SITE TIME"

    def lifetime_totals(self, session):
        return "Incursion lifetime", self.tracker.totals(INCURSION)

    def start_args(self):
        if self.auto_log.get() and not self.per_site.get().strip():
            return {}  # sites take their payout from the journal
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
        if self.auto_log.get():  # the payout would log the same site again
            raise ValueError("Sites are logged from EVE; switch off Log payouts from EVE to log by hand.")
        payout = parse_isk(self.payout.get(), "payout")
        minutes = self.timer_or(self.minutes, "site time")
        return self.tracker.log_incursion_site(self.session_id, payout, minutes)

    def after_log(self):
        self.minutes.delete(0, "end")

    def edit_fields(self, run):
        return [("Payout (M)", f"{run.profit:g}"), ("Site time (min)", f"{run.minutes:g}")]

    def save_edit(self, run, payout, minutes):
        return self.tracker.edit_incursion_site(
            run.id, parse_isk(payout, "payout"), parse_minutes(minutes, "site time")
        )

    def update_stats(self, session, runs):
        self.stats["profit"].set(signed_isk(session.profit), profit_color(session.profit))
        self.stats["rate"].set(format_isk(session.isk_per_hour))
        self.stats["time"].set(format_minutes(session.minutes), sub=f"{session.runs} sites" if runs else "")
        self.stats["avg"].set(format_minutes(session.minutes / session.runs) if session.runs else "—")


class ProfitChart(tk.Canvas):
    """Bar chart of profit per session, oldest to newest, with a hover tooltip."""

    PAD_L, PAD_R, PAD_T, PAD_B = 64, 8, 12, 26

    def __init__(self, master, theme):
        super().__init__(master, bg=theme.panel, highlightthickness=0, height=220)
        self.theme = theme
        self.sessions = []
        self.bars = []  # (x0, x1, session, cx)
        self.bind("<Configure>", lambda _e: self.draw())
        self.bind("<Motion>", self._hover)
        self.bind("<Leave>", lambda _e: self.delete("tip"))

    def show(self, sessions):
        """Draw the given sessions, newest first as from Tracker.sessions()."""
        self.sessions = list(reversed(sessions))
        self.draw()

    def draw(self):
        self.delete("all")
        self.bars = []
        t = self.theme
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        if not self.sessions:
            self.create_text(w / 2, h / 2, text="No sessions yet", fill=t.soft, font=canvas_font(11))
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
            self.create_line(self.PAD_L, y(v), w - self.PAD_R, y(v),
                             fill=t.line if v == 0 else mix(t.line, t.panel, 0.5))
            self.create_text(self.PAD_L - 10, y(v), text=format_isk(v), anchor="e", fill=t.soft,
                             font=canvas_font(9))
            v += step

        slot = (w - self.PAD_L - self.PAD_R) / len(self.sessions)
        bar_w = max(3, min(28, slot * 0.68))
        label_every = max(1, int(70 // slot) + 1)
        last = len(self.sessions) - 1
        for i, s in enumerate(self.sessions):
            cx = self.PAD_L + slot * (i + 0.5)
            self._bar(cx - bar_w / 2, cx + bar_w / 2, y(0), y(s.profit), KIND_COLOR[s.kind])
            self.bars.append((self.PAD_L + slot * i, self.PAD_L + slot * (i + 1), s, cx))
            if (i % label_every == 0 and last - i >= label_every) or i == last:
                self.create_text(cx, h - self.PAD_B + 14, text=f"{s.started_at:%d %b}", fill=t.soft,
                                 font=canvas_font(9))

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
        for x0, x1, s, cx in self.bars:
            if x0 <= event.x < x1:
                break
        else:
            return
        t = self.theme
        tier = f" {tier_label(s.tier)}" if s.tier is not None else ""
        lines = [
            f"{session_label(s)}{tier} · {s.started_at:%a %d %b %Y, %H:%M}",
            f"Profit  {signed_isk(s.profit)}",
            f"{s.runs} {'runs' if s.kind == ABYSS else 'sites'} · {format_minutes(s.minutes)}",
            f"ISK/hr  {format_isk(s.isk_per_hour)}",
        ]
        self.create_line(cx, self.PAD_T, cx, self.winfo_height() - self.PAD_B, fill=t.line, dash=(2, 3), tags="tip")
        text = self.create_text(0, 0, text="\n".join(lines), anchor="nw", fill=INK,
                                font=canvas_font(10), tags="tip")
        bx0, by0, bx1, by1 = self.bbox(text)
        tw, th = bx1 - bx0 + 34, by1 - by0 + 16
        tx = cx + 12 if cx + 12 + tw < self.winfo_width() else cx - 12 - tw
        ty = min(max(self.PAD_T, event.y - th / 2), self.winfo_height() - th - 4)
        box = self.create_rectangle(tx, ty, tx + tw, ty + th, fill=t.bg, outline=t.line, tags="tip")
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


def session_label(session):
    """What a session was: its weather, 'Incursion', or 'Abyss' when no weather was recorded."""
    return session.weather or KIND_NAME[session.kind]


def session_color(session):
    """The accent of the session's weather or of incursions; abyss orange when no weather was recorded."""
    if session.kind == ABYSS and not session.weather:
        return KIND_COLOR[ABYSS]
    return theme_for(session.kind, session.weather).accent


class WeatherRates(tk.Canvas):
    """ISK/hour for each abyssal weather and for incursions as bars, with a line about the best weather."""

    ROW = 30
    BEST = 34  # height of the best-weather line under the bars

    def __init__(self, master, theme):
        super().__init__(master, bg=theme.panel, highlightthickness=0, height=self.BEST)
        self.theme = theme
        self.rows = []
        self.best = ""
        self.bind("<Configure>", lambda _e: self.draw())

    def show(self, rows, best):
        """
        Args:
            rows (list[tuple[str, Totals | None, str, bool]]): (name, totals, accent, dimmed) per row.
            best (str): The line under the bars.
        """
        self.rows = rows
        self.best = best
        self.configure(height=self.ROW * len(rows) + self.BEST)
        self.draw()

    def draw(self):
        self.delete("all")
        t = self.theme
        w = self.winfo_width()
        if w < 50:
            return
        widest = max((abs(totals.isk_per_hour) for _, totals, _, _ in self.rows if totals), default=0) or 1
        x0, x1 = 100, w - 76
        for i, (name, totals, accent, dimmed) in enumerate(self.rows):
            fade = (lambda c: mix(c, t.panel, 0.55)) if dimmed else (lambda c: c)
            y = self.ROW * i + self.ROW / 2
            self.create_text(0, y, text=name, anchor="w", fill=fade(INK), font=canvas_font(12))
            self._pill(x0, x1, y, fade(mix(INK, t.panel, 0.92)))
            if totals:
                rate = totals.isk_per_hour
                self._pill(x0, x0 + max(10, (x1 - x0) * abs(rate) / widest), y,
                           fade(accent if rate >= 0 else CRITICAL_TEXT))
            self.create_text(w, y, text=format_isk(totals.isk_per_hour) if totals else "—", anchor="e",
                             fill=fade(INK), font=canvas_font(12, "bold"))
        self.create_text(0, self.ROW * len(self.rows) + self.BEST / 2, text=self.best, anchor="w", fill=t.soft,
                         font=canvas_font(11))

    def _pill(self, x0, x1, y, color):
        r = 5
        self.create_rectangle(x0 + r, y - r, x1 - r, y + r, fill=color, width=0)
        self.create_oval(x0, y - r, x0 + 2 * r, y + r, fill=color, width=0)
        self.create_oval(x1 - 2 * r, y - r, x1, y + r, fill=color, width=0)


class SessionTable(ctk.CTkFrame):
    """Table of past sessions, newest first, with a delete button on each row."""

    def __init__(self, master, theme, columns, on_delete):
        super().__init__(master, fg_color=theme.panel, corner_radius=12)
        self.theme = theme
        self.columns = columns  # list of (heading, width, anchor)
        self.on_delete = on_delete
        header = ctk.CTkFrame(self, fg_color="transparent", height=32)
        header.pack(fill="x", padx=12, pady=(8, 0))
        self._layout(header)
        for i, (heading, _, anchor) in enumerate(columns):
            ctk.CTkLabel(header, text=heading, font=font(12), text_color=theme.soft, anchor=anchor).grid(
                row=0, column=i, sticky="ew", padx=6
            )
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=theme.line,
                                           scrollbar_button_hover_color=theme.soft)
        self.body.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self.empty = ctk.CTkLabel(self.body, text="", text_color=theme.soft, font=font(13))

    def _layout(self, frame):
        for i, (_, width, _) in enumerate(self.columns):
            frame.grid_columnconfigure(i, minsize=width, weight=1 if width == 0 else 0)
        frame.grid_columnconfigure(len(self.columns), minsize=36)

    def show(self, rows, empty_text):
        """
        Args:
            rows (list[tuple[int, list[tuple]]]): (session id, cells) per row. A cell is
                (text, color), or (text, color, dot color) for a coloured dot before the text.
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
        for session_id, cells in rows:
            ctk.CTkFrame(self.body, fg_color=self.theme.line, height=1).pack(fill="x", padx=8)
            row = ctk.CTkFrame(self.body, fg_color="transparent", height=36)
            row.pack(fill="x", padx=8)
            self._layout(row)
            for i, (text, color, *dot) in enumerate(cells):
                cell = ctk.CTkFrame(row, fg_color="transparent")
                cell.grid(row=0, column=i, sticky="ew", padx=6, pady=3)
                if dot:
                    ctk.CTkFrame(cell, width=8, height=8, corner_radius=4, fg_color=dot[0]).pack(
                        side="left", padx=(0, 8)
                    )
                ctk.CTkLabel(cell, text=text, text_color=color, font=font(14), anchor=self.columns[i][2]).pack(
                    side="left", fill="x", expand=True
                )
            ctk.CTkButton(
                row, text="×", width=28, height=24, fg_color="transparent", hover_color=self.theme.line,
                text_color=self.theme.soft, command=lambda s=session_id: self.on_delete(s),
            ).grid(row=0, column=len(cells), padx=(4, 0))


class HistoryPage(ctk.CTkFrame):
    """
    Lifetime totals, profit per session, ISK/hour by weather and the list of past
    sessions, in the neutral Filament theme whatever the weather.
    """

    FILTERS = {"All": None, "Abyss": ABYSS, "Incursion": INCURSION}
    CHART_SESSIONS = 40  # most recent sessions shown in the chart
    theme = NEUTRAL_THEME

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.tracker = app.tracker
        t = self.theme

        # Shown on the right of the app header while this page is open
        self.toolbar = ctk.CTkFrame(app.header, fg_color="transparent")
        self.span = ctk.CTkLabel(self.toolbar, text="", font=font(13), text_color=t.soft)
        self.span.pack(side="left", padx=(0, 14))
        for text, width, command in (
            ("Import Sessions.txt", 160, self.import_txt),
            ("Export CSV", 100, self.export_csv),
            ("Back up", 80, self.back_up),
            ("Restore", 80, self.restore),
        ):
            ctk.CTkButton(
                self.toolbar, text=text, width=width, height=34, fg_color="transparent", border_width=1,
                border_color=t.line, hover_color=t.panel, text_color=INK, command=command,
            ).pack(side="left", padx=(0, 8))

        self.filter = ChipGroup(self, list(self.FILTERS), "All", lambda _v: self.refresh())
        self.filter.set_theme(t)
        self.filter.pack(anchor="w")

        totals = ctk.CTkFrame(self, fg_color="transparent")
        totals.pack(fill="x", pady=(14, 16))
        net = ctk.CTkFrame(totals, fg_color="transparent")
        net.pack(side="left", anchor="s", padx=(0, 44))
        self.net_label = ctk.CTkLabel(net, text="", font=font(13), text_color=t.soft, height=18)
        self.net_label.pack(anchor="w")
        self.net = ctk.CTkLabel(net, text="", font=font(64, "bold"), text_color=t.accent, height=70)
        self.net.pack(anchor="w")
        self.cells = {}
        for key in ("rate", "runs", "time", "wins"):
            cell = ctk.CTkFrame(totals, fg_color="transparent")
            cell.pack(side="left", anchor="s", padx=(0, 44), pady=(0, 6))
            label = ctk.CTkLabel(cell, text="", font=font(12), text_color=t.soft, height=16)
            label.pack(anchor="w")
            value = ctk.CTkLabel(cell, text="", font=font(26, "bold"), text_color=INK, height=32)
            value.pack(anchor="w")
            self.cells[key] = (label, value)

        middle = ctk.CTkFrame(self, fg_color="transparent")
        middle.pack(fill="x")
        middle.grid_columnconfigure(0, weight=1)
        middle.grid_columnconfigure(1, minsize=340)

        chart_card = ctk.CTkFrame(middle, fg_color=t.panel, corner_radius=12)
        chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        top = ctk.CTkFrame(chart_card, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(14, 6))
        self.chart_title = ctk.CTkLabel(top, text="", font=font(13), text_color=t.soft, height=18)
        self.chart_title.pack(side="left")
        for kind in (INCURSION, ABYSS):  # packed from the right
            ctk.CTkLabel(top, text=KIND_NAME[kind], font=font(13), text_color=t.soft, height=18).pack(
                side="right", padx=(0, 0 if kind == INCURSION else 18)
            )
            ctk.CTkFrame(top, width=10, height=10, corner_radius=2, fg_color=KIND_COLOR[kind]).pack(
                side="right", padx=(0, 6)
            )
        self.chart = ProfitChart(chart_card, t)
        self.chart.pack(fill="x", padx=12, pady=(0, 12))

        rates_card = ctk.CTkFrame(middle, fg_color=t.panel, corner_radius=12)
        rates_card.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(rates_card, text="ISK / hour by weather", font=font(13), text_color=t.soft, height=18).pack(
            anchor="w", padx=18, pady=(14, 8)
        )
        self.rates = WeatherRates(rates_card, t)
        self.rates.pack(fill="x", padx=18, pady=(0, 12))

        self.table = SessionTable(
            self, t,
            [("Date", 170, "w"), ("Weather", 170, "w"), ("Tier", 120, "w"), ("Runs", 60, "e"), ("Time", 0, "e"),
             ("Profit", 110, "e"), ("ISK / hr", 110, "e")],
            self.delete_session,
        )
        self.table.pack(fill="both", expand=True, pady=(14, 0))

    def refresh(self):
        name = self.filter.get()
        kind = self.FILTERS[name]
        totals = self.tracker.totals(kind)
        self.net_label.configure(text=f"{'ALL ACTIVITY' if kind is None else name.upper()}  ·  NET PROFIT")
        self.net.configure(text=signed_isk(totals.profit),
                           text_color=self.theme.accent if totals.profit >= 0 else CRITICAL_TEXT)
        for key, label, value in (
            ("rate", "ISK / hour", format_isk(totals.isk_per_hour)),
            ("runs", "Sites" if kind == INCURSION else "Runs", str(totals.runs)),
            ("time", "Time", format_minutes(totals.minutes)),
            ("wins", "Winning sessions", f"{totals.wins} / {totals.sessions}"),
        ):
            self.cells[key][0].configure(text=label)
            self.cells[key][1].configure(text=value)

        sessions = [s for s in self.tracker.sessions(kind) if s.runs]
        dated = [s.started_at for s in sessions if s.started_at.year != 1970]
        self.span.configure(text=_date_span(min(dated), max(dated)) if dated else "")

        shown = sessions[:self.CHART_SESSIONS]
        self.chart_title.configure(
            text=f"Profit per session  ·  {'last ' if len(sessions) > len(shown) else ''}"
                 f"{len(shown)} session{'s' if len(shown) != 1 else ''}"
        )
        self.chart.show(shown)

        # Every weather and incursions, dimming the ones the filter leaves out
        by_weather = self.tracker.totals_by_weather()
        incursions = self.tracker.totals(INCURSION)
        rates = [(w, by_weather.get(w), theme_for(ABYSS, w).accent, kind == INCURSION) for w in WEATHERS]
        rates.append(("Incursion", incursions if incursions.sessions else None, theme_for(INCURSION, None).accent,
                      kind == ABYSS))
        best = best_weather(by_weather)
        self.rates.show(rates, f"Best: {best} at {format_isk(by_weather[best].isk_per_hour)}/hr" if best
                        else "Best: log abyss runs with a weather to compare")

        rows = []
        for s in sessions[:300]:
            status = " · live" if s.active else " · txt" if s.imported else ""
            rows.append((s.id, [
                ("undated" if s.started_at.year == 1970 else f"{s.started_at:%d %b %Y  %H:%M}", self.theme.soft),
                (session_label(s) + status, GOOD_TEXT if s.active else INK, session_color(s)),
                (tier_label(s.tier) if s.tier is not None else "—", self.theme.soft),
                (str(s.runs), INK),
                (format_minutes(s.minutes), INK),
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

    def export_csv(self):
        name = self.filter.get()
        path = filedialog.asksaveasfilename(
            parent=self, title="Export CSV", defaultextension=".csv", initialfile=f"abyss-tracker-{name.lower()}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            count = self.tracker.export_csv(path, self.FILTERS[name])
        except OSError as err:
            messagebox.showerror("Export failed", str(err), parent=self)
            return
        messagebox.showinfo("Export", f"Exported {count} row{'s' if count != 1 else ''}.", parent=self)

    def back_up(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Back up tracker.db", defaultextension=".db",
            initialfile=f"tracker-{datetime.now():%Y-%m-%d}.db",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.tracker.backup(path)
        except (OSError, ValueError, sqlite3.Error) as err:
            messagebox.showerror("Backup failed", str(err), parent=self)
            return
        messagebox.showinfo("Backup", "Backup saved.", parent=self)

    def restore(self):
        path = filedialog.askopenfilename(
            parent=self, title="Restore from backup", filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        if not path or not messagebox.askyesno(
            "Restore backup",
            "Replace all sessions and runs with this backup?\n\nEverything logged since it was made is lost. "
            "This can't be undone.",
            parent=self,
        ):
            return
        try:
            self.tracker.restore(path)
        except (OSError, ValueError, sqlite3.Error) as err:
            messagebox.showerror("Restore failed", str(err), parent=self)
            return
        for kind in (ABYSS, INCURSION):  # a live session id may now point at nothing, or at a different session
            self.app.pages[kind].resume()
        messagebox.showinfo("Restore", "Backup restored.", parent=self)
        self.app.refresh()


def _date_span(first, last):
    """'01 Sep to 23 Oct 2026', with both years when they differ."""
    start = f"{first:%d %b}" if first.year == last.year else f"{first:%d %b %Y}"
    return f"{start} to {last:%d %b %Y}"


class SettingsPage(ctk.CTkFrame):
    """Sign in with EVE SSO, sign out and pick the active character."""

    theme = NEUTRAL_THEME
    toolbar = None
    session_id = None

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        t = self.theme
        card = ctk.CTkFrame(self, corner_radius=12, border_width=1, fg_color=t.panel, border_color=t.line)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=40, anchor="w")
        ctk.CTkLabel(inner, text="EVE account", font=font(20, "bold"), text_color=INK).pack(anchor="w")
        ctk.CTkLabel(
            inner, font=font(13), text_color=t.soft, justify="left", wraplength=560,
            text="Sign in with your EVE character so the app can read your wallet. Your browser opens "
                 "for the CCP login; the app never sees your password.",
        ).pack(anchor="w", pady=(4, 20))
        self.active = ctk.CTkLabel(inner, text="", font=font(15), text_color=INK)
        self.active.pack(anchor="w")
        self.characters = ctk.CTkFrame(inner, fg_color="transparent")
        self.characters.pack(anchor="w", pady=(10, 0))
        buttons = ctk.CTkFrame(inner, fg_color="transparent")
        buttons.pack(anchor="w", pady=(20, 0))
        self.sign_in_btn = ctk.CTkButton(
            buttons, text="Sign in with EVE", height=40, width=180, font=font(14, "bold"),
            fg_color=t.accent, hover_color=accent_hover(t), text_color=t.bg, command=self.sign_in,
        )
        self.sign_in_btn.pack(side="left")
        ctk.CTkButton(
            buttons, text="Sign out", height=40, width=120, fg_color="transparent", border_width=1,
            border_color=t.line, hover_color=t.panel, text_color=INK, command=self.sign_out,
        ).pack(side="left", padx=(12, 0))
        self.message = ctk.CTkLabel(inner, text="", font=font(12), wraplength=560, justify="left")
        self.message.pack(anchor="w", pady=(10, 0))

    def say(self, text, color=None):
        self.message.configure(text=text, text_color=color or self.theme.soft)

    def refresh(self):
        for child in self.characters.winfo_children():
            child.destroy()
        try:
            active = self.app.account.active()
            characters = self.app.account.characters()
        except SIGN_IN_ERRORS as e:
            self.active.configure(text="Sign-in unavailable")
            self.say(str(e), CRITICAL_TEXT)
            return
        self.active.configure(text=f"Active character: {active.name if active else 'none'}")
        for c in characters:
            on = active is not None and c.id == active.id
            ctk.CTkButton(
                self.characters, text=c.name + ("  ●" if on else ""), height=32, width=0,
                fg_color=self.theme.accent if on else "transparent", border_width=1,
                border_color=self.theme.line, hover_color=self.theme.line,
                text_color=self.theme.bg if on else INK,
                command=lambda cid=c.id: self.select(cid),
            ).pack(side="left", padx=(0, 8))

    def select(self, character_id):
        self.app.account.select(character_id)
        self.refresh()

    def sign_in(self):
        self.sign_in_btn.configure(state="disabled")
        self.say("Waiting for the browser sign-in (5 minutes)...")

        def done(character, error):
            self.sign_in_btn.configure(state="normal")
            if error is not None:
                self.say(str(error), CRITICAL_TEXT)
            else:
                self.say(f"Signed in as {character.name}.", GOOD_TEXT)
            self.refresh()

        self.app.run_async(self.app.account.sign_in, done)

    def sign_out(self):
        def done(gone, error):
            if error is not None:
                self.say(str(error), CRITICAL_TEXT)
            else:
                self.say(f"Signed out {gone.name}." if gone else "Nobody is signed in.")
            self.refresh()

        self.app.run_async(self.app.account.sign_out, done)  # revoking calls the network


class PocketOverlay(Painter, ctk.CTkToplevel):
    """
    A small always-on-top window to keep beside the EVE client: the timer, one field
    and the Log button, the session's key numbers and its last few runs.

    It drives the Abyss and Incursion pages, so it shares their timers, forms and
    sessions with the full window.
    """

    RECENT = 3  # runs listed

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.painters = []
        self.theme = None
        self._message_job = None
        self._tick_job = None
        with_session = next((k for k in (ABYSS, INCURSION) if app.pages[k].session_id), ABYSS)
        self.kind = app.current if app.current in (ABYSS, INCURSION) else with_session

        self.title("Abyss Tracker")
        self.resizable(False, False)
        self.minsize(380, 0)
        self.pinned = True  # always on top
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", app.leave_pocket)
        if sys.platform == "win32":  # CTkToplevel sets its own icon after 200 ms
            self.after(250, lambda: self.iconbitmap(asset_path("icon.ico")))
        self.paint(self, fg_color="bg")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=14)

        # Header: activity tabs, then pin and expand on the right
        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x")
        tab_bar = self.paint(ctk.CTkFrame(header, corner_radius=10), fg_color="panel")
        tab_bar.pack(side="left")
        self.tabs = {}
        for i, kind in enumerate((ABYSS, INCURSION)):
            self.tabs[kind] = ctk.CTkButton(tab_bar, text=KIND_NAME[kind], width=0, height=34, corner_radius=8,
                                            font=font(13, "bold"), command=lambda k=kind: self.switch(k))
            self.tabs[kind].pack(side="left", padx=(3, 3 if i else 0), pady=3)
        self.expand_btn = self.paint(
            ctk.CTkButton(header, text="Expand", width=0, height=40, font=font(13), command=app.leave_pocket),
            fg_color="panel", hover_color="line", text_color="soft",
        )
        self.expand_btn.pack(side="right")
        self.pin_btn = ctk.CTkButton(header, text="", width=0, height=40, font=font(13, "bold"),
                                     command=self.toggle_pin)
        self.pin_btn.pack(side="right", padx=(0, 6))
        self.painters.append(lambda _t: self._show_pin())

        # Timer: caption and state, the countdown, time left, start/pause and reset
        timer_card = self.paint(ctk.CTkFrame(body, corner_radius=16), fg_color="panel")
        timer_card.pack(fill="x", pady=(12, 0))
        top = ctk.CTkFrame(timer_card, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(14, 0))
        self.caption = self.paint(ctk.CTkLabel(top, text="", font=font(12), height=18), text_color="soft")
        self.caption.pack(side="left")
        self.clock_state = ctk.CTkLabel(top, text="", font=font(12), height=18)
        self.clock_state.pack(side="right")
        self.clock = self.paint(tk.Canvas(timer_card, height=84, highlightthickness=0), bg="panel")
        self.clock.pack(fill="x", padx=18)
        self.digits = FixedDigits(self.clock, -76, align="left")
        self.digits.place(0, 44)
        self.progress = self.paint(ctk.CTkProgressBar(timer_card, height=6, corner_radius=3), fg_color="line")
        self.timer_buttons = ctk.CTkFrame(timer_card, fg_color="transparent")
        self.timer_buttons.pack(fill="x", padx=18, pady=(0, 18))
        self.timer_buttons.grid_columnconfigure((0, 1), weight=1, uniform="timer")
        self.toggle_btn = self.paint(
            ctk.CTkButton(self.timer_buttons, text="", height=44, font=font(14, "bold"), text_color=INK,
                          command=self.toggle_timer),
            fg_color="line", hover_color=lambda t: mix(t.line, INK, 0.15),
        )
        self.toggle_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.reset_btn = self.paint(
            ctk.CTkButton(self.timer_buttons, text="Reset", height=44, font=font(14), fg_color="transparent",
                          border_width=1, command=self.reset_timer),
            border_color="line", hover_color="line", text_color="soft",
        )
        self.reset_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # Live session: the field and Log button, three numbers, the last runs
        self.live = ctk.CTkFrame(body, fg_color="transparent")
        form = self.paint(ctk.CTkFrame(self.live, corner_radius=16), fg_color="panel")
        form.pack(fill="x", pady=(12, 0))
        self.amount_label = self.paint(ctk.CTkLabel(form, text="", font=font(12), height=18), text_color="soft")
        self.amount_label.pack(anchor="w", padx=14, pady=(12, 0))
        self.amount = self.paint(ctk.CTkEntry(form, height=46, font=font(20, "bold"), text_color=INK,
                                              placeholder_text="million ISK"),
                                 fg_color="bg", border_color="line")
        self.amount.pack(fill="x", padx=14, pady=(4, 0))
        self.amount.bind("<Return>", lambda _e: self.log())
        self.log_btn = self.paint(
            ctk.CTkButton(form, text="", height=50, corner_radius=12, font=font(16, "bold"), command=self.log),
            **PRIMARY,
        )
        self.log_btn.pack(fill="x", padx=14, pady=(10, 0))
        self.message = ctk.CTkLabel(form, text="", font=font(12), height=18, wraplength=330, justify="left")
        self.message.pack(anchor="w", padx=14, pady=(4, 8))

        stats = ctk.CTkFrame(self.live, fg_color="transparent")
        stats.pack(fill="x", pady=(12, 0))
        stats.grid_columnconfigure((0, 1, 2), weight=1, uniform="stat")
        self.stats = []
        for i in range(3):
            tile = self.paint(ctk.CTkFrame(stats, corner_radius=12), fg_color="panel")
            tile.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0 if i == 2 else 4))
            label = self.paint(ctk.CTkLabel(tile, text="", font=font(11), height=16), text_color="soft")
            label.pack(anchor="w", padx=12, pady=(10, 0))
            value = ctk.CTkLabel(tile, text="", font=font(20, "bold"), height=26)
            value.pack(anchor="w", padx=12, pady=(0, 10))
            self.stats.append((label, value))

        runs_card = self.paint(ctk.CTkFrame(self.live, corner_radius=16), fg_color="panel")
        runs_card.pack(fill="x", pady=(12, 0))
        self.runs = ctk.CTkFrame(runs_card, fg_color="transparent")
        self.runs.pack(fill="x", padx=14, pady=(6, 0))
        footer = ctk.CTkFrame(runs_card, fg_color="transparent")
        footer.pack(fill="x", padx=14, pady=(6, 10))
        self.session_total = self.paint(ctk.CTkLabel(footer, text="", font=font(12), height=18), text_color="soft")
        self.session_total.pack(side="left")
        self.lifetime = self.paint(ctk.CTkLabel(footer, text="", font=font(12), height=18), text_color="soft")
        self.lifetime.pack(side="right")

        # No session: the full window starts one
        self.idle = self.paint(ctk.CTkFrame(body, corner_radius=16), fg_color="panel")
        self.idle_text = self.paint(ctk.CTkLabel(self.idle, text="", font=font(14)), text_color="soft")
        self.idle_text.pack(anchor="w", padx=18, pady=(16, 8))
        self.paint(
            ctk.CTkButton(self.idle, text="Expand to start one", height=44, font=font(14, "bold"),
                          command=app.leave_pocket),
            **PRIMARY,
        ).pack(anchor="w", padx=18, pady=(0, 18))

        self.refresh()
        self._load_amount()
        self._tick()

    @property
    def page(self):
        return self.app.pages[self.kind]

    def switch(self, kind):
        """Show the other activity here, and in the full window for when it expands."""
        self.kind = kind
        self.app.show(kind)
        self.refresh()
        self._load_amount()
        self.say("")

    def refresh(self):
        page = self.page
        if page.theme != self.theme:
            self.theme = page.theme
            self.repaint(self.theme)
        for kind, btn in self.tabs.items():
            style_tab(btn, KIND_NAME[kind], kind == self.kind, self.app.pages[kind].session_id, self.theme)
        timer_name = "time left" if page.timer.countdown else "site time"
        session = self.app.tracker.session(page.session_id) if page.session_id else None
        if session is None:
            self.live.pack_forget()
            self.idle.pack(fill="x", pady=(12, 0))
            self.idle_text.configure(text=f"No {KIND_NAME[self.kind].lower()} session running.")
            self.caption.configure(text=timer_name.capitalize())
            self._render_clock()
            return

        self.idle.pack_forget()
        self.live.pack(fill="x")
        unit = page.unit.capitalize()
        self.caption.configure(text=f"{unit} {session.runs + 1} · {timer_name}")
        self.amount_label.configure(text=page.pocket_label)
        self.log_btn.configure(text=f"Log {page.unit} · uses timer")
        for (label, value), (text, number, color) in zip(self.stats, (
            ("Profit", signed_isk(session.profit), profit_color(session.profit)),
            ("ISK/hr", format_isk(session.isk_per_hour), INK),
            (f"{unit}s", str(session.runs), INK),
        )):
            label.configure(text=text)
            value.configure(text=number, text_color=color)
        self.show_runs(self.app.tracker.runs(session.id), page.unit)
        self.session_total.configure(text=f"Session {signed_isk(session.profit)} · {format_minutes(session.minutes)}")
        label, totals = page.lifetime_totals(session)
        self.lifetime.configure(text=f"{label} {signed_isk(totals.profit)}" if totals else "")
        self._render_clock()

    def show_runs(self, runs, unit):
        """The last few runs, newest first, each with its number, duration and profit."""
        for child in self.runs.winfo_children():
            child.destroy()
        if not runs:
            ctk.CTkLabel(self.runs, text=f"No {unit}s yet.", font=font(14), text_color=self.theme.soft,
                         height=40).pack(anchor="w")
            return
        for number, run in list(enumerate(runs, 1))[-self.RECENT:][::-1]:
            row = ctk.CTkFrame(self.runs, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=str(number), width=22, anchor="w", font=font(14), text_color=self.theme.soft,
                         height=40).pack(side="left")
            ctk.CTkLabel(row, text=format_minutes(run.minutes), font=font(14), text_color=INK_2,
                         height=40).pack(side="left", padx=(8, 0))
            ctk.CTkLabel(row, text=signed_isk(run.profit), font=font(14, "bold"), text_color=profit_color(run.profit),
                         height=40).pack(side="right")
            ctk.CTkFrame(self.runs, height=1, corner_radius=0, fg_color=self.theme.line).pack(fill="x")

    def log(self):
        if self.page.session_id is None:
            return
        try:
            run = self.page.pocket_log(self.amount.get())
        except ValueError as err:
            self.say(str(err), CRITICAL_TEXT)
            return
        self._load_amount()
        self.say(logged_text(run), profit_color(run.profit))

    def _load_amount(self):
        """Copy the page's field, e.g. the incursion payout that stays between sites."""
        set_entry(self.amount, self.page.pocket_fields()[0].get())

    def hand_back(self):
        """Give the page a value typed here but not logged, before the full window returns."""
        if self.amount.get():
            set_entry(self.page.pocket_fields()[0], self.amount.get())

    def say(self, text, color=None):
        self.message.configure(text=text, text_color=color or self.theme.soft)
        if self._message_job:
            self.after_cancel(self._message_job)
        self._message_job = self.after(5000, lambda: self.message.configure(text=""))

    def toggle_pin(self):
        # Kept here: on X11, -topmost reads back the old value until the window manager answers
        self.pinned = not self.pinned
        self.attributes("-topmost", self.pinned)
        self._show_pin()

    def _show_pin(self):
        self.pin_btn.configure(
            text="Unpin" if self.pinned else "Pin on top", fg_color=self.theme.panel, hover_color=self.theme.line,
            text_color=self.theme.accent if self.pinned else self.theme.soft,
        )

    def toggle_timer(self):
        self.page.timer.toggle()
        self._render_clock()

    def reset_timer(self):
        self.page.timer.reset()
        self._render_clock()

    def _tick(self):
        self._render_clock()
        self._tick_job = self.after(250, self._tick)

    def _render_clock(self):
        timer = self.page.timer
        face = timer.face()
        color = digit_color(face, self.theme)
        self.digits.show(face.text, color)
        self.clock_state.configure(text=face.state, text_color=self.theme.soft if face.state == "ready" else color)
        self.toggle_btn.configure(text=timer.toggle_text(face))
        if face.share_left is None:  # the stopwatch has no end
            self.progress.pack_forget()
            return
        if not self.progress.winfo_manager():
            self.progress.pack(fill="x", padx=18, pady=(0, 12), before=self.timer_buttons)
        self.progress.configure(progress_color=color)
        self.progress.set(face.share_left)

    def destroy(self):
        if self._tick_job:
            self.after_cancel(self._tick_job)
        if self._message_job:
            self.after_cancel(self._message_job)
        super().destroy()


class App(ctk.CTk):
    TABS = [("abyss", "Session"), ("incursion", "Incursion"), ("history", "History"), ("settings", "Settings")]

    def __init__(self, tracker=None):
        super().__init__(fg_color=NEUTRAL_THEME.bg)
        self.tracker = tracker or Tracker()
        self.account = Account()
        self.title("Abyss Tracker")
        self.geometry("1180x800")
        self.minsize(1000, 700)
        self.set_icon()
        self.use_ui_font()

        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=32, pady=(22, 0))
        ctk.CTkLabel(self.header, text="ABYSS TRACKER", font=font(18, "bold"), text_color=INK).pack(side="left")
        self.tab_bar = ctk.CTkFrame(self.header, corner_radius=10)
        self.tab_bar.pack(side="left", padx=20)
        self.tabs = {}
        for i, (key, label) in enumerate(self.TABS):
            btn = ctk.CTkButton(
                self.tab_bar, text=label, width=0, height=36, corner_radius=8, font=font(14, "bold"),
                command=lambda k=key: self.show(k),
            )
            btn.pack(side="left", padx=(3, 0 if i < len(self.TABS) - 1 else 3), pady=3)
            self.tabs[key] = btn
            self.bind(f"<Control-Key-{i + 1}>", lambda _e, k=key: self.show(k))
        self.pocket = None  # the PocketOverlay while it replaces this window
        self.pocket_btn = ctk.CTkButton(self.header, text="Pocket mode", width=0, height=34, fg_color="transparent",
                                        border_width=1, text_color=INK, command=self.enter_pocket)
        self.pocket_btn.pack(side="right", padx=(10, 0))  # page toolbars pack to its left

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32, pady=(18, 24))
        self.pages = {
            "abyss": AbyssPage(content, self),
            "incursion": IncursionPage(content, self),
            "history": HistoryPage(content, self),
            "settings": SettingsPage(content, self),
        }

        self.current = None
        for page in ("abyss", "incursion"):
            self.pages[page].resume()
        active = next((k for k in ("abyss", "incursion") if self.pages[k].session_id), "abyss")
        self.show(active)
        self.after(150, self.bring_to_front)

    def run_async(self, work, done):
        """Run `work()` off the UI thread, then call `done(result, error)` on it."""
        outcome = []

        def target():
            try:
                outcome.append((work(), None))
            except Exception as e:
                outcome.append((None, e))

        threading.Thread(target=target, daemon=True).start()

        def poll():
            if outcome:
                done(*outcome[0])
            else:
                self.after(100, poll)

        poll()

    def use_ui_font(self):
        """
        Draw every widget in the bundled font, or in the platform's UI font when
        it did not load. Runs before any widget exists, as CTkFont reads the
        default family when each font is created.
        """
        global UI_FAMILY
        fallback = tkfont.nametofont("TkDefaultFont", root=self).actual("family")
        UI_FAMILY = ui_family(tkfont.families(self), fallback)
        ctk.ThemeManager.theme["CTkFont"]["family"] = UI_FAMILY

    def set_icon(self):
        """Window and taskbar icon: .ico on Windows, PNG elsewhere."""
        if sys.platform == "win32":
            self.iconbitmap(asset_path("icon.ico"))
        else:
            # Keep a reference: Tk drops the image once Python garbage-collects it
            self.icon = tk.PhotoImage(file=asset_path("icon.png"))
            self.iconphoto(True, self.icon)

    def bring_to_front(self):
        """macOS often opens Tk windows behind the terminal; raise and focus it."""
        if self.pocket:  # the overlay is standing in for this window
            return
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def show(self, key):
        if self.current:
            self.pages[self.current].pack_forget()
            if self.pages[self.current].toolbar:
                self.pages[self.current].toolbar.pack_forget()
        self.current = key
        page = self.pages[key]
        page.refresh()
        page.pack(fill="both", expand=True)
        if page.toolbar:
            page.toolbar.pack(side="right")
        self.apply_theme(page.theme)

    def apply_theme(self, theme):
        """Colour the window and header for the page that is showing."""
        self.configure(fg_color=theme.bg)
        self.tab_bar.configure(fg_color=theme.panel)
        self.pocket_btn.configure(border_color=theme.line, hover_color=theme.panel)
        for name, btn in self.tabs.items():
            live = name in ("abyss", "incursion") and self.pages[name].session_id
            style_tab(btn, dict(self.TABS)[name], name == self.current, live, theme)

    def refresh(self):
        """Refresh the visible page and the pocket overlay; hidden pages refresh when shown."""
        self.show(self.current)
        if self.pocket:
            self.pocket.refresh()

    def enter_pocket(self):
        """Swap this window for the small always-on-top overlay."""
        if self.pocket is None:
            self.pocket = PocketOverlay(self)
        self.withdraw()

    def leave_pocket(self):
        """Close the overlay and bring this window back."""
        if self.pocket is not None:
            self.pocket.hand_back()
            self.pocket.destroy()
            self.pocket = None
        self.deiconify()
        self.refresh()
        self.lift()
        self.focus_force()


def main():
    if tk.TkVersion < 8.6:
        raise SystemExit(
            f"This Python uses Tk {tk.TkVersion}, which is too old to show the window "
            f"(Apple's built-in /usr/bin/python3 does this).\n"
            "Install Python from python.org, or on Homebrew: brew install python python-tk"
        )
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    load_fonts()
    App().mainloop()


if __name__ == "__main__":
    main()
