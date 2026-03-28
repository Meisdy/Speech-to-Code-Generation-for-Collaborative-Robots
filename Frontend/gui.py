"""
GUI module for Speech-to-Code Framework for Collaborative Robots.
Pure view layer — emits events and displays data, contains no business logic.
"""

import logging
import threading
from tkinter import scrolledtext
from typing import Callable

import tkinter as tk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import LEFT, BOTH, X, PRIMARY

from Frontend.config_frontend import ROBOT_TYPE_KEYS

logger = logging.getLogger("cobot")


class UserGUI:
    """Pure view layer for the Speech-to-Code application."""

    def __init__(
        self,
        on_record_start: Callable[[], None],
        on_record_stop: Callable[[str], None],
        on_ping: Callable[[str], None],
        on_confirm: Callable[[str], None],
        on_discard: Callable[[], None],
        on_stop: Callable[[str], None],
    ) -> None:
        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop
        self.on_ping = on_ping
        self.on_confirm = on_confirm
        self.on_discard = on_discard
        self.on_stop = on_stop

        self.root = ttkb.Window(themename="darkly")
        self.root.title("Speech-to-Code Generation for Cobots")
        self.root.geometry("1000x700")
        self.root.minsize(600, 500)

        self.robot_type: tk.StringVar = tk.StringVar(value=next(iter(ROBOT_TYPE_KEYS)))

        self.record_btn: ttkb.Button | None = None
        self.stop_btn: ttkb.Button | None = None
        self.status_label: ttkb.Label | None = None
        self.log_text: scrolledtext.ScrolledText | None = None
        self.robot_combo: ttkb.Combobox | None = None
        self._led: tk.Canvas | None = None
        self._confirmation_panel: ttkb.LabelFrame | None = None
        self._confirmation_steps_frame: ttkb.Frame | None = None
        self._log_frame: ttkb.LabelFrame | None = None
        self._space_down: bool = False

        self._setup_ui()
        self._bind_events()

    def set_connection_status(self, status: str) -> None:
        """Update the backend LED. status: 'unknown' | 'ok' | 'error'."""
        colours = {"ok": "#28a745", "error": "#dc3545", "unknown": "#6c757d"}
        self._led.itemconfig("led", fill=colours.get(status, "#6c757d"))

    def set_gui_status_line(self, message: str, style: str = "info") -> None:
        """Update the status label text and style."""
        self.status_label.configure(text=message, bootstyle=style)

    def set_button_state(self, text: str, style: str = "primary", enabled: bool = True) -> None:
        """Update the record button text, style, and enabled state."""
        state = "normal" if enabled else "disabled"
        self.record_btn.configure(text=text, bootstyle=style, state=state)
        self.robot_combo.configure(state="readonly" if enabled else "disabled")

    def show_confirmation_panel(self, script_name: str, steps: list[str], on_edit: Callable[[int], None]) -> None:
        """Display the script confirmation panel with pre-formatted step strings and per-step edit buttons."""
        self._confirmation_panel.configure(text=f"📋 Confirm Script: '{script_name}'")

        # Destroy old step rows before rebuilding
        for widget in self._confirmation_steps_frame.winfo_children():
            widget.destroy()

        for i, step in enumerate(steps, start=1):
            row = ttkb.Frame(self._confirmation_steps_frame)
            row.pack(fill=X, pady=1)
            ttkb.Label(row, text=f"{i}.  {step}", font=("Consolas", 10), anchor="w").pack(
                side=LEFT, fill=X, expand=True)
            ttkb.Button(row, text="🔄", bootstyle="secondary", width=3,
                        command=lambda idx=i - 1: on_edit(idx)).pack(side=LEFT)

        self._confirmation_panel.pack(fill=X, padx=30, pady=(0, 10), before=self._log_frame)

    def hide_confirmation_panel(self) -> None:
        """Remove the script confirmation panel from the layout."""
        self._confirmation_panel.pack_forget()

    def show_stop_button(self) -> None:
        """Show the stop button below the record button."""
        self.stop_btn.pack(after=self.record_btn, pady=(0, 10), ipadx=40, ipady=12)

    def hide_stop_button(self) -> None:
        """Remove the stop button from the layout."""
        self.stop_btn.pack_forget()

    def log(self, message: str, level: int = logging.INFO) -> None:
        """Append a log message to the log area with level-based colouring."""
        if threading.current_thread() is not threading.main_thread():
            logger.error("gui.log() called from non-main thread — skipping")
            return

        level_name = logging.getLevelName(level)
        if not isinstance(level_name, str):
            level_name = "INFO"

        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{message}\n", level_name)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def run(self) -> None:
        """Start the GUI main event loop."""
        self.root.mainloop()

    def on_window_close(self, cleanup_callback: Callable[[], None]) -> None:
        """Register a callback to run when the window is closed."""
        def close_handler():
            cleanup_callback()
            self.root.destroy()
        self.root.protocol("WM_DELETE_WINDOW", close_handler)

    def _on_ping_click(self) -> None:
        """Redirect focus to root before firing ping so the button loses its focus ring."""
        self.root.focus_set()
        self.on_ping(self.robot_type.get())

    def _setup_ui(self) -> None:
        """Build and layout all GUI widgets."""
        header = ttkb.Frame(self.root)
        header.pack(fill=X, pady=(20, 10), padx=30)

        ttkb.Label(header, text="🎤 Speech-to-Code for Cobots",
                   font=("Segoe UI", 24, "bold")).pack(pady=(0, 10))
        ttkb.Label(header, text="Press & hold button or use SPACEBAR to record commands",
                   font=("Segoe UI", 12)).pack(pady=(0, 20))

        robot_frame = ttkb.Frame(self.root)
        robot_frame.pack(pady=(10, 4), padx=30)

        ttkb.Label(robot_frame, text="Robot Type:", font=("Segoe UI", 11)).pack(side=LEFT)
        self.robot_combo = ttkb.Combobox(
            robot_frame,
            textvariable=self.robot_type,
            values=list(ROBOT_TYPE_KEYS.keys()),
            state="readonly",
            font=("Segoe UI", 11),
            width=13
        )
        self.robot_combo.pack(side=LEFT, padx=(10, 0))

        ttkb.Button(
            robot_frame, text="Ping Backend", bootstyle="secondary",
            takefocus=0, command=self._on_ping_click
        ).pack(side=LEFT, padx=(20, 6), ipady=2)

        self._led = tk.Canvas(robot_frame, width=14, height=14, highlightthickness=0,
                              bg=self.root.style.colors.bg)
        self._led.create_oval(2, 2, 12, 12, fill="#6c757d", outline="", tags="led")
        self._led.pack(side=LEFT)

        self.record_btn = ttkb.Button(self.root, text="Press and hold to record", bootstyle=PRIMARY)
        self.record_btn.pack(pady=40, ipadx=80, ipady=25)

        # Created here but not packed — shown only during SCRIPT_RUNNING
        self.stop_btn = ttkb.Button(
            self.root, text="⏹ Stop Script", bootstyle="danger",
            command=lambda: self.on_stop(self.robot_type.get())
        )

        self.status_label = ttkb.Label(
            self.root,
            text="Ready – Select cobot & start commanding!",
            font=("Segoe UI", 13)
        )
        self.status_label.pack(pady=20, padx=30)

        # Created here but not packed — shown only during SCRIPT_CONFIRMING
        self._setup_confirmation_panel()

        self._log_frame = ttkb.LabelFrame(self.root, text="📋 Log")
        self._log_frame.pack(fill=BOTH, padx=30, pady=20, expand=True)

        log_inner = ttkb.Frame(self._log_frame)
        log_inner.pack(fill=BOTH, expand=True, padx=15, pady=15)

        self.log_text = scrolledtext.ScrolledText(
            log_inner,
            height=12,
            font=("Consolas", 10),
            state="disabled",
            bg="#212529",
            fg="#f8f9fa",
            insertbackground="#f8f9fa"
        )
        self.log_text.pack(fill=BOTH, expand=True)

        self.log_text.tag_config("DEBUG",    foreground="#9AA5B1")
        self.log_text.tag_config("INFO",     foreground="#F8F9FA")
        self.log_text.tag_config("WARNING",  foreground="#FFC107")
        self.log_text.tag_config("ERROR",    foreground="#FF6B6B")
        self.log_text.tag_config("CRITICAL", foreground="#FF3B30", underline=True)

    def _setup_confirmation_panel(self) -> None:
        """Build the confirmation panel. Not packed until show_confirmation_panel is called."""
        self._confirmation_panel = ttkb.LabelFrame(self.root, text="📋 Confirm Script",
                                                   font=("Segoe UI", 11))

        # Container for dynamically built step rows
        self._confirmation_steps_frame = ttkb.Frame(self._confirmation_panel)
        self._confirmation_steps_frame.pack(fill=X, padx=15, pady=(10, 6))

        btn_frame = ttkb.Frame(self._confirmation_panel)
        btn_frame.pack(pady=(0, 12))

        ttkb.Button(
            btn_frame, text="✅ Confirm & Save", bootstyle="success",
            command=lambda: self.on_confirm(self.robot_type.get())
        ).pack(side=LEFT, padx=(0, 10), ipadx=20, ipady=6)

        ttkb.Button(
            btn_frame, text="❌ Discard", bootstyle="danger",
            command=self.on_discard
        ).pack(side=LEFT, ipadx=20, ipady=6)

    def _bind_events(self) -> None:
        """Bind mouse and keyboard events to their handlers."""
        self.record_btn.bind("<Button-1>", self._handle_press)
        self.record_btn.bind("<ButtonRelease-1>", self._handle_release)
        self.root.bind("<KeyPress-space>", self._handle_press)
        self.root.bind("<KeyRelease-space>", self._handle_release)
        self.root.focus_set()

    def _handle_press(self, event: tk.Event) -> str:
        """Handle button press or spacebar down."""
        if event.type == tk.EventType.KeyPress and event.keysym == "space":
            if self._space_down:
                return "break"
            self._space_down = True
        self.on_record_start()
        return "break"

    def _handle_release(self, event: tk.Event) -> str:
        """Handle button release or spacebar up."""
        if event.type == tk.EventType.KeyRelease and event.keysym == "space":
            self._space_down = False
        self.on_record_stop(self.robot_type.get())
        return "break"