from ASR_module import SpeechRecognizer
import threading
from enum import Enum, auto


class State(Enum):
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()



class Controller:
    def __init__(self):
        self.state = State.IDLE
        self.asr = SpeechRecognizer()
        self.gui = None

    def on_start(self):
        if self.state != State.IDLE:
            return  # Ignore if busy

        self.state = State.RECORDING
        self.gui.set_status("🔴 Recording...", "warning")
        self.gui.set_button_state("Press and hold to record (spacebar)", "warning", True)
        threading.Thread(target=self.asr.start_listening, daemon=True).start()

    def on_stop(self, robot_type: str):
        if self.state != State.RECORDING:
            return

        self.state = State.PROCESSING
        self.gui.set_status("Processing...", "info")
        self.gui.set_button_state("Press and hold to record (spacebar)", "info", True)
        threading.Thread(target=lambda: self._process(robot_type), daemon=True).start()

    def _process(self, robot_type):
        audio = self.asr.stop_listening()
        result = self.asr.transcribe(audio)

        self.gui.root.after(0, lambda: self._finish(result))

    def _finish(self, result):
        self.gui.display_result(result)
        self.state = State.IDLE

    # Link gui to controller during startup
    def set_gui(self, gui):
        self.gui = gui