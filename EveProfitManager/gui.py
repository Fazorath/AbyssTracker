"""
Desktop UI for the Abyss and Incursion tracker.

Run with:  python gui.py
"""
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import (
    ABYSS,
    INCURSION,
    MAXTIME,
    TIERS,
    WEATHERS,
    Tracker,
    format_isk,
    format_minutes,
    isk_per_hour,
    tier_label,
)
from theme import NEUTRAL_THEME, theme_for

# Dark theme tokens for the History page; session pages use the Filament theme
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


def font(size=13, weight="normal"):
    return ctk.CTkFont(size=size, weight=weight)


def mix(color, other, amount):
    """Blend two '#rrggbb' colours: amount 0 gives color, 1 gives other."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def accent_hover(theme):
    """Hover colour for accent-filled buttons."""
    return mix(theme.accent, theme.bg, 0.2)


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


# paint() options for accent-filled buttons
PRIMARY = {"fg_color": "accent", "hover_color": accent_hover, "text_color": "bg"}


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
        self.caption = self.create_text(0, 0, text="", font=("TkDefaultFont", -14))
        self.display = self.create_text(0, 0, text="", font=("Consolas", -132, "bold"))
        self.hint = self.create_text(0, 0, text="", font=("TkDefaultFont", -15))
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
        self.coords(self.display, cx, cy - 18)
        self.coords(self.hint, cx, cy + 62)
        self.coords(self.button_window, cx, cy + 122)

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
        color = self.theme.accent
        if self.countdown and elapsed > 0:
            if seconds < 120:
                color = CRITICAL_TEXT
            elif seconds < 300:
                color = WARNING
        self.itemconfigure(self.display, text=f"{mins:02d}:{secs:02d}", fill=color)

        if self.countdown and elapsed > 0 and seconds <= 0:
            hint = "Timer expired"
        elif self.theme.hint:
            hint = self.theme.hint
        elif elapsed > 0:
            hint = "Leave the time field blank to use this"
        else:
            hint = "Start when you enter" if self.countdown else "Start when the site starts"
        self.itemconfigure(self.hint, text=hint)
        self.toggle_btn.configure(text="Pause timer" if self.running else ("Resume" if elapsed > 0 else "Start timer"))


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


class RunLog(ctk.CTkFrame):
    """Table of the runs/sites in the current session, newest first."""

    def __init__(self, master, columns, on_delete, on_edit=None):
        super().__init__(master, fg_color=SURFACE, corner_radius=10, border_width=1, border_color=BORDER)
        self.columns = columns  # list of (heading, width, anchor)
        self.on_edit = on_edit
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
        for i in range(len(self.columns), len(self.columns) + (2 if self.on_edit else 1)):
            frame.grid_columnconfigure(i, minsize=36)

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
            actions = [("×", self.on_delete)]
            if self.on_edit:
                actions.insert(0, ("✎", self.on_edit))
            for i, (text, action) in enumerate(actions):
                ctk.CTkButton(
                    row, text=text, width=28, height=24, fg_color="transparent", hover_color=BORDER,
                    text_color=MUTED, command=lambda r=run_id, a=action: a(r),
                ).grid(row=0, column=len(cells) + i, padx=(4, 0))


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


class SessionPage(ctk.CTkFrame):
    """
    Shared layout for the Abyss and Incursion pages: a start screen and a live session
    screen, coloured by the session's Filament theme.
    """

    kind = None
    subtitle = ""
    unit = "run"

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
    def update_stats(self, session, runs): ...
    def timer_caption(self, session): return ""
    def lifetime_totals(self, session): return "", None
    def idle_theme(self): return theme_for(self.kind, None)
    def after_log(self): ...
    def edit_fields(self, run): return []
    def save_edit(self, run, *values): ...

    # --- shared behaviour -------------------------------------------------

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

    def set_theme(self, theme):
        """Recolour the page, and the app around it when the page is showing."""
        if theme == self.theme:
            return
        self.theme = theme
        for painter in self.painters:
            painter(theme)
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
        self.used_timer = False
        try:
            run = self.log_run()
        except ValueError as err:
            self.flash(str(err), CRITICAL_TEXT)
            return
        if self.used_timer:  # a typed time leaves a running timer alone
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

    def build_start_form(self, frame):
        self.start_isk = self.field(frame, 0, "Wallet now (million ISK)", 220, "e.g. 1,250 or 1.25b")
        self.start_isk.bind("<Return>", lambda _e: self.start_session())
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

    def build_timer(self, master):
        return TimerPanel(master, countdown_minutes=MAXTIME)

    def idle_theme(self):
        return theme_for(ABYSS, self.weather.get())

    def entries(self):
        return [self.after_isk, self.time_left]

    def stat_labels(self):
        return [("profit", "Session"), ("rate", "ISK/hr"), ("time", "Time"), ("wallet", "Wallet")]

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


class IncursionPage(SessionPage):
    kind = INCURSION
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
        self.payout = self.field(frame, 0, "Payout (M)", 110)
        self.minutes = self.field(frame, 1, "Site time (min)", 150, "blank = stopwatch")

    def build_timer(self, master):
        return TimerPanel(master)

    def entries(self):
        return [self.minutes, self.payout]

    def stat_labels(self):
        return [("profit", "Session"), ("rate", "ISK/hr"), ("time", "Time"), ("avg", "Avg site")]

    def timer_caption(self, session):
        return f"INCURSION  ·  SITE {session.runs + 1}  ·  SITE TIME"

    def lifetime_totals(self, session):
        return "Incursion lifetime", self.tracker.totals(INCURSION)

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
    theme = NEUTRAL_THEME
    toolbar = None

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
                ("undated" if s.started_at.year == 1970 else f"{s.started_at:%d %b %Y  %H:%M}", INK_2),
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
    TABS = [("abyss", "Session"), ("incursion", "Incursion"), ("history", "History")]

    def __init__(self, tracker=None):
        super().__init__(fg_color=NEUTRAL_THEME.bg)
        self.tracker = tracker or Tracker()
        self.title("Abyss Tracker")
        self.geometry("1180x800")
        self.minsize(1000, 700)

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

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32, pady=(18, 24))
        self.pages = {
            "abyss": AbyssPage(content, self),
            "incursion": IncursionPage(content, self),
            "history": HistoryPage(content, self),
        }

        self.current = None
        for page in ("abyss", "incursion"):
            self.pages[page].resume()
        active = next((k for k in ("abyss", "incursion") if self.pages[k].session_id), "abyss")
        self.show(active)
        self.after(150, self.bring_to_front)

    def bring_to_front(self):
        """macOS often opens Tk windows behind the terminal; raise and focus it."""
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
        for name, btn in self.tabs.items():
            on = name == self.current
            live = name in ("abyss", "incursion") and self.pages[name].session_id
            btn.configure(
                text=dict(self.TABS)[name] + ("  ●" if live else ""),
                fg_color=theme.accent if on else "transparent",
                hover_color=accent_hover(theme) if on else theme.line,
                text_color=theme.bg if on else theme.soft,
            )

    def refresh(self):
        """Refresh the visible page; hidden pages refresh when shown."""
        self.show(self.current)


def main():
    if tk.TkVersion < 8.6:
        raise SystemExit(
            f"This Python uses Tk {tk.TkVersion}, which is too old to show the window "
            f"(Apple's built-in /usr/bin/python3 does this).\n"
            "Install Python from python.org, or on Homebrew: brew install python python-tk"
        )
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    App().mainloop()


if __name__ == "__main__":
    main()
