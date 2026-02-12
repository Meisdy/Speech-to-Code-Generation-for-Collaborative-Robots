from ASR_module import SpeechRecognizer
import threading
from enum import Enum, auto


class State(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    #PARSING = auto()
    #EXECUTING = auto()


class Controller:
    def __init__(self):
        self.state = State.IDLE
        self.asr = SpeechRecognizer()
        self.gui = None

        # Recording thread control
        self.recording_active = threading.Event()
        self.recording_thread = None


    def start_recording(self):
        if self.state != State.IDLE:
            return  # Ignore if busy

        self.state = State.RECORDING
        self.gui.set_status("🔴 Recording...", "warning")
        self.gui.set_button_state("Press and hold to record (spacebar)", "warning", True)

        self.recording_active.set()
        self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.recording_thread.start()


    def _recording_loop(self):
        """Continuously record audio until recording_active is cleared."""
        self.asr.start_listening()  # Initialize recording resources
        while self.recording_active.is_set():
            self.asr.read_chunk()  # This will block until recording is stopped


    def start_execution(self, robot_type: str):
        if self.state != State.RECORDING:
            return

        # Update GUI immediately to show processing status while we wait for recording thread to finish
        self.state = State.TRANSCRIBING
        self.gui.set_status("Processing...", "info")
        self.gui.set_button_state("Press and hold to record (spacebar)", "info", False)

        # Stop recording thread and wait for it to finish before processing audio
        self.recording_active.clear()  # Signal recording thread to stop
        if self.recording_thread:
            self.recording_thread.join()  # Wait for recording thread to finish
            self.recording_thread = None

        threading.Thread(target=lambda: self._process_audio(robot_type), daemon=True).start()


    def _process_audio(self, robot_type):
        audio = self.asr.stop_listening()
        result = self.asr.transcribe(audio)
        self.gui.root.after(0, lambda: self._finish(result))

    def _finish(self, result):
        self.gui.display_result(result)
        self.state = State.IDLE

    # Link gui to controller during startup
    def set_gui(self, gui):
        self.gui = gui