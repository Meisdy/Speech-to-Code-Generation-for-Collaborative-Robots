"""
GUI module for Speech-to-Code Framework for Collaborative Robots.

This module provides a modern GUI interface for recording voice commands
and converting them to robot code using speech recognition.
"""

import threading
import tkinter as tk
import ttkbootstrap as ttkb
from tkinter import scrolledtext
from datetime import datetime
from typing import Callable, Dict, Any
from ttkbootstrap.constants import *


class UserGUI:
    """Main GUI class for the Speech-to-Code application."""

    def __init__(self, process_speech: Callable[[str], Dict[str, Any]]) -> None:
        """
        Initialize the GUI.

        Args:
            process_speech: Callback function that processes speech input.
                           Takes robot_type (str) and returns dict with
                           'text' and 'confidence' keys.
        """
        self.process_speech = process_speech
        self.root = ttkb.Window(themename="darkly")
        self.root.title("Speech-to-Code Generation for Cobots")
        self.root.geometry("1000x700")
        self.root.minsize(600, 500)

        # State management
        self.is_recording: bool = False
        self.robot_type: tk.StringVar = tk.StringVar(value="Franka Emika")

        # Widget references (initialized in setup_ui)
        self.record_btn: ttkb.Button
        self.status_label: ttkb.Label
        self.log_text: scrolledtext.ScrolledText

        self.setup_ui()
        self.bind_spacebar()

    def setup_ui(self) -> None:
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
            text="Press & hold button or SPACEBAR to record commands",
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
            values=["Franka Emika", "Universal Robots", "Mock Robot"],
            state="readonly",
            font=("Segoe UI", 11),
            width=15
        )
        robot_combo.pack(side=LEFT, padx=(10, 0))

        # Main Record Button
        self.record_btn = ttkb.Button(
            self.root,
            text="Press and hold to record (spacebar)"
        )
        self.record_btn.pack(pady=40, ipadx=80, ipady=25)
        self.record_btn.configure(bootstyle=PRIMARY)
        self.bind_events()

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
            bg="#212529"
        )
        self.log_text.pack(fill=BOTH, expand=True)

    def bind_events(self) -> None:
        """Bind mouse events to the record button."""
        self.record_btn.bind("<Button-1>", self.on_press)
        self.record_btn.bind("<ButtonRelease-1>", self.on_release)

    def bind_spacebar(self) -> None:
        """Bind spacebar key events for recording."""
        self.root.bind("<space>", self.on_press)
        self.root.bind("<KeyRelease-space>", self.on_release)
        self.root.focus_set()

    def on_press(self, _: tk.Event) -> str:
        """
        Handle button press event.

        Args:
            _: Tkinter event (unused)

        Returns:
            "break" to prevent default behavior
        """
        if not self.is_recording:
            self.start_recording()
        return "break"

    def on_release(self, _: tk.Event) -> str:
        """
        Handle button release event.

        Args:
            _: Tkinter event (unused)

        Returns:
            "break" to prevent default behavior
        """
        if self.is_recording:
            self.stop_recording()
        return "break"

    def start_recording(self) -> None:
        """Start the recording process."""
        self.is_recording = True
        self.record_btn.configure(text="Recording...", bootstyle=WARNING)
        self.status_label.configure(
            text=f"🔴 Recording for {self.robot_type.get()}...",
            bootstyle=WARNING
        )
        self.log(f"Started recording for {self.robot_type.get()}")

    def stop_recording(self) -> None:
        """Stop recording and begin processing."""
        self.is_recording = False
        self.record_btn.configure(text="Processing...", bootstyle=INFO)
        self.status_label.configure(
            text=f"Processing for {self.robot_type.get()}...",
            bootstyle=INFO
        )
        threading.Thread(target=self.process_recording, daemon=True).start()

    def process_recording(self) -> None:
        """Process the recorded speech in a background thread."""
        try:
            result = self.process_speech(self.robot_type.get())
            self.root.after(0, lambda: self.update_result(result))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ Error: {e}"))

    def update_result(self, result: Dict[str, Any]) -> None:
        """
        Update UI with transcription results.

        Args:
            result: Dictionary containing 'text' and 'confidence' keys
        """
        text = result.get('text', 'N/A')
        conf = result.get('confidence', 0)
        self.log(
            f"✓ Transcribed: '{text}' (conf: {conf:.2f}) "
            f"for {self.robot_type.get()}"
        )
        self.status_label.configure(
            text=f"✅ Ready – Last: {text[:50]}...",
            bootstyle=SUCCESS
        )
        self.recording_done()

    def recording_done(self) -> None:
        """Reset UI to ready state after processing."""
        self.record_btn.configure(
            text="Press and hold to record (spacebar)",
            bootstyle=PRIMARY
        )
        self.status_label.configure(
            text=f"Ready for {self.robot_type.get()} – "
                 f"start recording!",
            bootstyle=INFO
        )

    def log(self, message: str) -> None:
        """
        Thread-safe logging to the log text widget.

        Args:
            message: Message to log
        """
        self.log_text.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def run(self) -> None:
        """Start the GUI main event loop."""
        self.root.mainloop()


def main() -> None:
    """Entry point for testing the GUI with a dummy processor."""
    def dummy_process(robot_type: str) -> Dict[str, Any]:
        """
        Simulate speech processing.

        Args:
            robot_type: Type of robot selected

        Returns:
            Dictionary with transcription result
        """
        import time
        time.sleep(2)
        return {
            "text": f"Move the {robot_type} forward",
            "confidence": 0.92
        }

    gui = UserGUI(process_speech=dummy_process)
    gui.run()


if __name__ == "__main__":
    main()
