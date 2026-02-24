import config
import threading
import logging
import json
from enum import Enum, auto
from parsing_module import CodeParser
from ASR_module import SpeechRecognizer
from communication_client import ClientZeroMQ


logger = logging.getLogger("cobot")


class State(Enum):
    """Pipeline execution states."""
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    PARSING = auto()
    EXECUTING = auto()


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
        self.client = ClientZeroMQ(config.BACKEND_IP)
        self.gui = None
        self.confidence_threshold = config.ASR_CONFIDENCE_THRESHOLD

        # Recording thread control
        self.recording_active = threading.Event()
        self.recording_thread = None


    def set_gui(self, gui):
        """Link GUI to controller during startup."""
        self.gui = gui

    def start_recording(self):
        """Begin audio recording if in IDLE state."""
        if self.state != State.IDLE:
            return  # Ignore if busy

        # Update state and GUI
        self.state = State.RECORDING
        self.gui.set_gui_status_line("🔴 Recording...", "warning")
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
        self.gui.set_gui_status_line("Processing...", "info")
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
            self.gui.set_gui_status_line("❌ Transcription failed", "danger")
            self._set_button_state()
            self.state = State.IDLE
            logger.error("Transcription failed: no text or zero confidence")
            return

        # Check for low confidence and warn user
        if result.get("confidence", 1) < self.confidence_threshold:
            logger.warning("ASR confidence low: %.2f - parsing may fail", result.get("confidence", 0.0))

        # Move to parsing state
        self.state = State.PARSING
        self.gui.set_gui_status_line("Parsing command...", "info")

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
            self.gui.set_gui_status_line("✅ Command parsed successfully", "success")
            logger.info(f'Parser: Command summary \"{command_as_string}\"')

            # Execute Backend now
            threading.Thread(
                target=lambda: self._send_command(parse_result["command"]),
                daemon=True
            ).start()

        else:
            error_msg = parse_result.get("error", "Unknown parsing error")
            self.gui.set_gui_status_line(f"❌ Parsing error", "danger")
            logger.error("Parsing failed: %s", error_msg)

        # Return to idle state
        self.state = State.IDLE
        self._set_button_state()

    def _send_command(self, command: dict):
        data = {
            "mode": "live",
            "robot": command["robot"],
            "commands": command.get("commands", []),
            "message": ""
        }
        logger.info('Client: Sending data to backend')
        logger.debug('Sending data: %s', json.dumps(data)[:500])

        success, response = self.client.send_command("execute_sequence", data)
        self.gui.root.after(0, lambda: self._display_execution_result(success, response))

    def _display_execution_result(self, success: bool, response: dict):
        if success and response.get("command") == "success":
            self.gui.set_gui_status_line("✅ Execution complete", "success")
            logger.debug("Execution: Backend executed command successfully: %s", response)
            logger.info("Execution: Backend executed command successfully. Details available in logfile")
        else:
            self.gui.set_gui_status_line("❌ Execution failed", "danger")
            logger.error("Execution: Backend failed to execute command: %s", response)
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

            # Action-specific formatting
            if action == "move":
                target = cmd.get("target", {})
                name = target.get("name", target) if isinstance(target, dict) else target
                parts.append(f"Move to {name} pos.")

            elif action == "gripper":
                state = cmd.get("state") or cmd.get("command", "?")
                parts.append(f"{state.capitalize()} gripper")

            elif action == "teach":
                parts.append(f"Teach position '{cmd.get('name', '?')}'")

            elif action == "wait":
                parts.append(f"Wait {cmd.get('duration', '?')}s")

            else:
                parts.append(action.capitalize())

        return " → ".join(parts)

    def _set_button_state(self, visual_state: str = "primary", enabled: bool = True):
        """Reset button state to default."""
        self.gui.set_button_state("Press and hold to record", visual_state, enabled)

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
            self.asr.close()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
