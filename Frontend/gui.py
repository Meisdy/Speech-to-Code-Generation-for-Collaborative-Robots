"""
GUI module for Speech-to-Code Framework for Collaborative Robots.

This module provides a pure view layer following MVP pattern.
The GUI emits events and displays data - contains no business logic.
"""

import config_frontend
import logging
import tkinter as tk
import ttkbootstrap as ttkb
from tkinter import scrolledtext
from typing import Callable, Optional
from ttkbootstrap.constants import LEFT, BOTH, X, PRIMARY



class UserGUI:
    """
    Pure View layer for Speech-to-Code application.

    Responsibilities:
    - Display UI elements (buttons, status, log)
    - Emit events to Presenter/Controller
    - Update display when told to

    Does NOT:
    - Manage state
    - Handle threading
    - Contain business logic
    """

    def __init__(self,on_record_start: Callable[[], None],on_record_stop: Callable[[str], None] ) -> None:
        """
        Initialize the GUI view.

        Args:
            on_record_start: Callback when user presses record button
            on_record_stop: Callback when user releases record button
                           Takes robot_type (str) as parameter
        """
        # Event callbacks (connect to Presenter)
        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop

        # Setup window
        self.root = ttkb.Window(themename="darkly")
        self.root.title("Speech-to-Code Generation for Cobots")
        self.root.geometry("1000x700")
        self.root.minsize(600, 500)

        # UI state for robot type selection (default value)
        self.robot_type: tk.StringVar = tk.StringVar(value="Franka Emika")
        self.robot_types = config_frontend.ROBOT_TYPES

        # Widget references with type hints for better readability and IDE support
        self.record_btn: ttkb.Button
        self.status_label: ttkb.Label
        self.log_text: scrolledtext.ScrolledText
        self._space_down: bool = False  # Track spacebar state to stop trigger spam of system

        # Widget references - initialize to None (explicit declaration)
        self.record_btn: Optional[ttkb.Button] = None
        self.status_label: Optional[ttkb.Label] = None
        self.log_text: Optional[scrolledtext.ScrolledText] = None

        # Build the UI and bind events
        self._setup_ui()
        self._bind_events()


    def _setup_ui(self) -> None:
        """Build and layout all GUI widgets."""
        # Header
        header = ttkb.Frame(self.root)
        header.pack(fill=X, pady=(20, 10), padx=30)

        title = ttkb.Label(
            header,
            text="🎤 Speech-to-Code for Cobots",
            font=("Segoe UI", 24, "bold")
        )
        title.pack(pady=(0, 10))

        subtitle = ttkb.Label(
            header,
            text="Press & hold button or use SPACEBAR to record commands",
            font=("Segoe UI", 12)
        )
        subtitle.pack(pady=(0, 20))

        # Robot Type Dropdown
        robot_frame = ttkb.Frame(self.root)
        robot_frame.pack(pady=10, padx=30)

        ttkb.Label(
            robot_frame,
            text="Robot Type:",
            font=("Segoe UI", 11)
        ).pack(side=LEFT)

        robot_combo = ttkb.Combobox(
            robot_frame,
            textvariable=self.robot_type,
            values=self.robot_types,
            state="readonly",
            font=("Segoe UI", 11),
            width=12
        )
        robot_combo.pack(side=LEFT, padx=(10, 0))

        # Main Record Button
        self.record_btn = ttkb.Button(
            self.root,
            text="Press and hold to record"
        )
        self.record_btn.pack(pady=40, ipadx=80, ipady=25)
        self.record_btn.configure(bootstyle=PRIMARY)

        # Status Field
        self.status_label = ttkb.Label(
            self.root,
            text="Ready – Select cobot & start recording!",
            font=("Segoe UI", 13)
        )
        self.status_label.pack(pady=20, padx=30)

        # Log Area
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

        # Configure text tags for colored log levels
        # Keep colors minimal and readable on dark background
        self.log_text.tag_config('DEBUG', foreground='#9AA5B1')   # dim gray
        self.log_text.tag_config('INFO', foreground='#F8F9FA')    # light/white
        self.log_text.tag_config('WARNING', foreground='#FFC107') # amber
        self.log_text.tag_config('ERROR', foreground='#FF6B6B')   # soft red
        self.log_text.tag_config('CRITICAL', foreground='#FF3B30', underline=True)

    def _bind_events(self) -> None:
        """Bind user input events to emit callbacks."""
        # Mouse events on button
        self.record_btn.bind("<Button-1>", self._handle_press)
        self.record_btn.bind("<ButtonRelease-1>", self._handle_release)

        # Keyboard events
        self.root.bind("<KeyPress-space>", self._handle_press)
        self.root.bind("<KeyRelease-space>", self._handle_release)
        self.root.focus_set() # Ensure root window has focus to capture key events

    def _handle_press(self, event: tk.Event) -> str:
        """Internal handler for press events (mouse or keyboard)."""
        if event.type == tk.EventType.KeyPress and event.keysym == "space":
            if self._space_down:
                return "break"  # ignore auto-repeat
            self._space_down = True

        self.on_record_start()
        return "break"

    def _handle_release(self, event: tk.Event) -> str:
        """Internal handler for release events (mouse or keyboard)."""
        if event.type == tk.EventType.KeyRelease and event.keysym == "space":
            self._space_down = False

        robot_type = self.robot_type.get()
        self.on_record_stop(robot_type)
        return "break"

    # ========== PUBLIC METHODS FOR PRESENTER TO UPDATE VIEW ==========

    def set_gui_status_line(self, message: str, style: str = "info") -> None:
        """
        Update status label (called by Presenter).

        Args:
            message: Status text to display
            style: Bootstrap style (info, success, warning, danger, primary)
        """
        self.status_label.configure(text=message, bootstyle=style)

    def set_button_state(self, text: str, style: str = "primary", enabled: bool = True) -> None:
        """
        Update record button (called by Presenter).

        Args:
            text: Button text
            style: Bootstrap style
            enabled: Whether button is clickable
        """
        self.record_btn.configure(text=text, bootstyle=style)
        if enabled:
            self.record_btn.configure(state="normal")
        else:
            self.record_btn.configure(state="disabled")

    def log(self, message: str, level: int = logging.INFO) -> None:
        """
        Append message to log area with optional level for coloring.

        Args:
            message: Log message to display
            level: logging level (int) - controls color/tag
        """
        # Determine tag name from level
        level_name = logging.getLevelName(level)
        if not isinstance(level_name, str):
            level_name = 'INFO'

        # Ensure GUI update happens on main thread; callers from GuiHandler already schedule via after
        self.log_text.config(state="normal") # Enable editing to insert log
        self.log_text.insert(tk.END, f"{message}\n", level_name)
        self.log_text.see(tk.END) # Auto-scroll to latest entry
        self.log_text.config(state="disabled") # Disable editing again

    def run(self) -> None:
        """Start the GUI main event loop."""
        self.root.mainloop()

    def on_window_close(self, cleanup_callback: Callable[[], None]) -> None:
        """Register callback to run on window close."""

        def close_handler():
            cleanup_callback()
            self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", close_handler)


# Testing stub
def main() -> None:
    """Test GUI with dummy callbacks."""
    def on_start():
        print("Presenter: Recording started")
        gui.set_button_state('Press and hold to record', 'warning', True)
        gui.set_gui_status_line("🔴 Recording...", "warning")
        gui.log("Recording started")

    def on_stop(robot_type: str):
        print(f"Presenter: Recording stopped for {robot_type}")
        gui.set_button_state('Press and hold to record', 'info', True)
        gui.set_gui_status_line("Processing...", "info")
        gui.log(f"Processing for {robot_type}...")

        # Simulate async result after 2s
        def show_result():
            result = {
                "text": f"Move the {robot_type} forward",
                "confidence": 0.92,
                "status": "success"
            }
            gui.log(str(result))

        gui.root.after(2000, show_result)

    gui = UserGUI(on_record_start=on_start, on_record_stop=on_stop)
    gui.run()

if __name__ == "__main__":
    main()
