# gui.py - Modern Speech-to-Code GUI for Cobot Programming (Button Render Fixed)

import tkinter as tk
from tkinter import scrolledtext
import threading
from datetime import datetime
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *


class UserGUI:
    def __init__(self, process_speech):
        self.process_speech = process_speech
        self.root = ttkb.Window(themename="darkly")
        self.root.title("Speech-to-Code Generation for Cobots")
        self.root.geometry("1000x700")
        self.root.minsize(600, 500)

        self.is_recording = False
        self.robot_type = tk.StringVar(value="Franka Emika")

        self.setup_ui()
        self.bind_spacebar()

    def setup_ui(self):
        # Header
        header = ttkb.Frame(self.root)
        header.pack(fill=X, pady=(20, 10), padx=30)
        title = ttkb.Label(header, text="🎤 Speech-to-Code for Cobots", font=("Segoe UI", 24, "bold"))
        title.pack(pady=(0, 10))
        subtitle = ttkb.Label(header, text="Press & hold button or SPACEBAR to record commands", font=("Segoe UI", 12))
        subtitle.pack(pady=(0, 20))

        # Robot Type Dropdown
        robot_frame = ttkb.Frame(self.root)
        robot_frame.pack(pady=10, padx=30)
        ttkb.Label(robot_frame, text="Robot Type:", font=("Segoe UI", 11)).pack(side=LEFT)
        robot_combo = ttkb.Combobox(robot_frame, textvariable=self.robot_type,
                                    values=["Franka Emika", "Universal Robots", "Mock Robot"],
                                    state="readonly", font=("Segoe UI", 11), width=15)
        robot_combo.pack(side=LEFT, padx=(10, 0))

        # Main Record Button (pure bootstyle - renders immediately)
        self.record_btn = ttkb.Button(self.root, text="Press and hold to record (spacebar)")
        self.record_btn.pack(pady=40, ipadx=80, ipady=25)
        self.record_btn.configure(bootstyle=PRIMARY)  # Force initial style load
        self.bind_events()

        # Status Field
        self.status_label = ttkb.Label(self.root, text="Ready – Select cobot & start recording!", font=("Segoe UI", 13))
        self.status_label.pack(pady=20, padx=30)

        # Log Area
        log_outer = ttkb.LabelFrame(self.root, text="📋 Log")
        log_outer.pack(fill=BOTH, padx=30, pady=20, expand=True)
        log_inner = ttkb.Frame(log_outer)
        log_inner.pack(fill=BOTH, expand=True, padx=15, pady=15)
        self.log_text = scrolledtext.ScrolledText(log_inner, height=12, font=("Consolas", 10),
                                                  state="disabled", bg="#212529")
        self.log_text.pack(fill=BOTH, expand=True)

    def bind_events(self):
        self.record_btn.bind("<Button-1>", self.on_press)
        self.record_btn.bind("<ButtonRelease-1>", self.on_release)
        self.record_btn.bind("<Enter>", self.on_enter)
        self.record_btn.bind("<Leave>", self.on_leave)

    def on_enter(self, event):
        if not self.is_recording:
            self.record_btn.configure(bootstyle=SUCCESS)

    def on_leave(self, event):
        if not self.is_recording:
            self.record_btn.configure(bootstyle=PRIMARY)

    def bind_spacebar(self):
        self.root.bind("<space>", self.on_press_space)
        self.root.bind("<KeyRelease-space>", self.on_release_space)
        self.root.focus_set()

    def on_press(self, event):
        if not self.is_recording:
            self.start_recording()
        return "break"

    def on_release(self, event):
        if self.is_recording:
            self.stop_recording()
        return "break"

    def on_press_space(self, event):
        self.on_press(event)
        return "break"

    def on_release_space(self, event):
        self.on_release(event)
        return "break"

    def start_recording(self):
        self.is_recording = True
        self.record_btn.configure(text="Recording...", bootstyle=WARNING)
        self.status_label.configure(text=f"🔴 Recording for {self.robot_type.get()}...",
                                    bootstyle=WARNING)
        self.log(f"Started recording for {self.robot_type.get()}")

    def stop_recording(self):
        self.is_recording = False
        self.record_btn.configure(text="Processing...", bootstyle=INFO)
        self.status_label.configure(text=f"Processing for {self.robot_type.get()}...",
                                    bootstyle=INFO)
        threading.Thread(target=self.process_recording, daemon=True).start()

    def process_recording(self):
        try:
            result = self.process_speech(self.robot_type.get())
            self.root.after(0, lambda: self.update_result(result))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ Error: {e}"))

    def update_result(self, result: dict):
        text = result.get('text', 'N/A')
        conf = result.get('confidence', 0)
        self.log(f"✓ Transcribed: '{text}' (conf: {conf:.2f}) for {self.robot_type.get()}")
        self.status_label.configure(text=f"✅ Ready – Last: {text[:50]}...", bootstyle=SUCCESS)
        self.recording_done()

    def recording_done(self):
        self.record_btn.configure(text="Press and hold to record (spacebar)", bootstyle=PRIMARY)
        self.status_label.configure(text=f"Ready for {self.robot_type.get()} – Press and hold to record (spacebar)",
                                    bootstyle=INFO)

    def log(self, message: str):
        self.log_text.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    def dummy_process(robot_type):
        import time
        time.sleep(2)  # Simulate processing delay
        return {"text": f"Move the {robot_type} forward", "confidence": 0.92}


    gui = UserGUI(process_speech=dummy_process)
    gui.run()
