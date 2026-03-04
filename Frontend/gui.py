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

    def __init__(self, on_record_start: Callable[[], None], on_record_stop: Callable[[str], None]) -> None:
        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop

        self.root = ttkb.Window(themename="darkly")
        self.root.title("Speech-to-Code Generation for Cobots")
        self.root.geometry("1000x700")
        self.root.minsize(600, 500)

        # Default to first configured robot type
        self.robot_type: tk.StringVar = tk.StringVar(value=next(iter(ROBOT_TYPE_KEYS)))

        self.record_btn: ttkb.Button | None = None
        self.status_label: ttkb.Label | None = None
        self.log_text: scrolledtext.ScrolledText | None = None
        self._space_down: bool = False  # Prevents OS key-repeat from firing multiple press events

        self._setup_ui()
        self._bind_events()

    def set_gui_status_line(self, message: str, style: str = "info") -> None:
        """Update the status label text and style."""
        self.status_label.configure(text=message, bootstyle=style)

    def set_button_state(self, text: str, style: str = "primary", enabled: bool = True) -> None:
        """Update the record button text, style, and enabled state."""
        state = "normal" if enabled else "disabled"
        self.record_btn.configure(text=text, bootstyle=style, state=state)

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

    def _setup_ui(self) -> None:
        """Build and layout all GUI widgets."""
        header = ttkb.Frame(self.root)
        header.pack(fill=X, pady=(20, 10), padx=30)

        ttkb.Label(header, text="🎤 Speech-to-Code for Cobots", font=("Segoe UI", 24, "bold")).pack(pady=(0, 10))
        ttkb.Label(header, text="Press & hold button or use SPACEBAR to record commands", font=("Segoe UI", 12)).pack(pady=(0, 20))

        robot_frame = ttkb.Frame(self.root)
        robot_frame.pack(pady=10, padx=30)

        ttkb.Label(robot_frame, text="Robot Type:", font=("Segoe UI", 11)).pack(side=LEFT)
        ttkb.Combobox(
            robot_frame,
            textvariable=self.robot_type,
            values=list(ROBOT_TYPE_KEYS.keys()),
            state="readonly",
            font=("Segoe UI", 11),
            width=13
        ).pack(side=LEFT, padx=(10, 0))

        self.record_btn = ttkb.Button(self.root, text="Press and hold to record", bootstyle=PRIMARY)
        self.record_btn.pack(pady=40, ipadx=80, ipady=25)

        self.status_label = ttkb.Label(
            self.root,
            text="Ready – Select cobot & start commanding!",
            font=("Segoe UI", 13)
        )
        self.status_label.pack(pady=20, padx=30)

        log_outer = ttkb.LabelFrame(self.root, text="📋 Log")
        log_outer.pack(fill=BOTH, padx=30, pady=20, expand=True)

        log_inner = ttkb.Frame(log_outer)
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

        self.log_text.tag_config("DEBUG",    foreground="#9AA5B1")  # dim gray
        self.log_text.tag_config("INFO",     foreground="#F8F9FA")  # white
        self.log_text.tag_config("WARNING",  foreground="#FFC107")  # amber
        self.log_text.tag_config("ERROR",    foreground="#FF6B6B")  # soft red
        self.log_text.tag_config("CRITICAL", foreground="#FF3B30", underline=True)

    def _bind_events(self) -> None:
        """Bind mouse and keyboard events to their handlers."""
        self.record_btn.bind("<Button-1>", self._handle_press)
        self.record_btn.bind("<ButtonRelease-1>", self._handle_release)
        self.root.bind("<KeyPress-space>", self._handle_press)
        self.root.bind("<KeyRelease-space>", self._handle_release)
        self.root.focus_set()  # Root must have focus to receive keyboard events

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


def main() -> None:
    """Test GUI with dummy callbacks."""
    def on_start():
        gui.set_button_state("Press and hold to record", "warning", True)
        gui.set_gui_status_line("🔴 Recording...", "warning")
        gui.log("Recording started")

    def on_stop(robot_type: str):
        gui.set_button_state("Press and hold to record", "info", True)
        gui.set_gui_status_line("Processing...", "info")
        gui.log(f"Processing for {robot_type}...")
        gui.root.after(2000, lambda: gui.log(f"Result: move {robot_type} forward (confidence 0.92)"))

    gui = UserGUI(on_record_start=on_start, on_record_stop=on_stop)
    gui.run()

if __name__ == "__main__":
    main()