import time
import json
import config
import threading
import logging
from enum import Enum, auto
from parsing_module import CodeParser
from ASR_module import SpeechRecognizer


"""

Notes:
Input lagg when pressing recording button. Good if we can fix this
Positions and names with numbers maybe need a better llm prompt so we do not mix 1 and one
Still not sure if this is a real state machine. Check the run of GUI as well in depth
maybe update all gui stuff in one gui display handler that checks the state of the controller



"""

logger = logging.getLogger("cobot")


class State(Enum):
    """Pipeline execution states."""
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    PARSING = auto()


class Controller:
    """
    Main pipeline controller coordinating ASR, parsing, and GUI.

    Manages state transitions and orchestrates the speech-to-code workflow:
    IDLE → RECORDING → TRANSCRIBING → PARSING → IDLE
    """

    def __init__(self):
        """Initialize controller with ASR and parser modules."""
        self.state = State.IDLE
        self.asr = SpeechRecognizer()
        self.parser = CodeParser()
        self.gui = None
        self.confidence_threshold = config.ASR_CONFIDENCE_THRESHOLD

        # Recording thread control
        self.recording_active = threading.Event()
        self.recording_thread = None

        # Logging configuration
        self.log_dir: str = config.LOGGING_DIR
        self.log_audio: bool = config.LOGGING_SAVE_AUDIO
        self.log_parsing: bool = config.LOGGING_SAVE_PARSE

    def set_gui(self, gui):
        """Link GUI to controller during startup."""
        self.gui = gui

    def start_recording(self):
        """Begin audio recording if in IDLE state."""
        if self.state != State.IDLE:
            return  # Ignore if busy

        # Update state and GUI
        self.state = State.RECORDING
        self.gui.set_status("🔴 Recording...", "warning")
        self._set_button_state('warning', True)

        # Start recording thread
        self.recording_active.set()
        self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.recording_thread.start()

        logger.info("Recording started")

    def _recording_loop(self):
        """Continuously record audio until recording_active is cleared."""
        while self.recording_active.is_set():
            self.asr.read_chunk()

    def start_execution(self, robot_type: str):
        """
        Stop recording and begin processing pipeline.

        Args:
            robot_type: Target robot identifier for command parsing
        """
        if self.state != State.RECORDING:
            return

        # Update GUI to show processing
        self.state = State.TRANSCRIBING
        self.gui.set_status("Processing...", "info")
        self._set_button_state('info', False)

        # Stop recording thread and wait for completion
        self.recording_active.clear()
        if self.recording_thread:
            self.recording_thread.join()
            self.recording_thread = None

        logger.info("Recording stopped, starting transcription")

        # Process audio in background thread
        threading.Thread(target=lambda: self._process_audio(robot_type), daemon=True).start()

    def _process_audio(self, robot_type: str):
        """Transcribe audio and display result."""
        audio = self.asr.get_audio()
        result = self.asr.transcribe(audio)

        # Update GUI on main thread
        self.gui.root.after(0, lambda: self._display_transcribe_result(result, robot_type))

    def _display_transcribe_result(self, result: dict, robot_type: str):
        """
        Display transcription and trigger parsing.

        Args:
            result: Transcription result with 'text' and 'confidence'
            robot_type: Target robot for parsing
        """

        # Check if transcription was successful
        if not result.get("text") or result.get("confidence", 0) == 0:
            self.gui.set_status("❌ Transcription failed", "danger")
            self._set_button_state()
            self.state = State.IDLE
            logger.error("Transcription failed: no text or zero confidence")
            return

        # Check for low confidence and warn user
        if result.get("confidence", 1) < self.confidence_threshold:
            logger.warning("ASR confidence low: %.2f - parsing may fail", result.get("confidence", 0.0))

        # Move to parsing state
        self.state = State.PARSING
        self.gui.set_status("Parsing command...", "info")

        # Parse in background thread
        threading.Thread(target=lambda: self._parse_command(result["text"], robot_type), daemon=True).start()

    def _parse_command(self, text: str, robot_type: str):
        """
        Parse natural language to robot command.

        Args:
            text: Transcribed text from ASR
            robot_type: Target robot identifier
        """
        parse_result = self.parser.parse(text, robot_type)

        # Update GUI on main thread
        self.gui.root.after(0, lambda: self._display_parse_result(parse_result))

    def _display_parse_result(self, parse_result: dict):
        """
        Display parsing result and return to idle.

        Args:
            parse_result: Parser output with 'status', 'command', and optional 'error'
        """

        if parse_result["status"] == "success":
            command_as_string = self._command_to_string(parse_result["command"])
            self.gui.set_status("✅ Command parsed successfully", "success")
            logger.info(f'Parser: Command summary \"{command_as_string}\"')

            # save the parsed command if logging is enabled
            if self.log_parsing:
                timestamp = time.strftime("%y%m%d_%H%M%S")
                filename = f"{self.log_dir}/{timestamp}_parse_result.json"
                with open(filename, "w") as f:
                    json.dump(parse_result["command"], f, indent=4)
                logger.info(f"Parser: Saved parsed command to {filename}")

        else:
            error_msg = parse_result.get("error", "Unknown parsing error")
            self.gui.set_status(f"❌ {error_msg}", "danger")
            logger.error("Parsing failed: %s", error_msg)

        # Return to idle state
        self.state = State.IDLE
        self._set_button_state()

    def _command_to_string(self, command: dict) -> str:
        """Convert command JSON to human-readable string for logging."""
        commands = command.get("commands", [])
        if not commands:
            return "Empty command"

        parts = []
        for cmd in commands:
            action = cmd.get("action", "unknown")

            if action == "move":
                target = cmd.get("target", {})
                # Handle dictionary target
                if isinstance(target, dict):
                    name = target.get("name", "?")
                    parts.append(f"Move to {name} pos.")
                else:
                    parts.append(f"Move to {target} pos.")

            elif action == "gripper":
                state = cmd.get("state", cmd.get("command", "?"))  # Try both 'state' and 'command'
                parts.append(f"{state.capitalize()} gripper")

            elif action == "teach":
                name = cmd.get("name", "?")
                parts.append(f"Teach position '{name}'")

            elif action == "wait":
                duration = cmd.get("duration", "?")
                parts.append(f"Wait {duration}s")

            else:
                parts.append(f"{action.capitalize()}")

        return " → ".join(parts)

    def cleanup(self):
        """Clean up resources on shutdown."""
        try:
            # Stop recording if active
            if self.recording_active.is_set():
                self.recording_active.clear()
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=1.0)

            # Now actually close the stream
            if self.asr.is_listening():
                self.asr.close()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

    # Helper method to reset button state after processing
    def _set_button_state(self, visual_state: str = "primary", enabled: bool = True):
        """Reset button state to default."""
        self.gui.set_button_state("Press and hold to record", visual_state, enabled)

