"""Pipeline controller coordinating ASR, parsing, and backend communication."""

import json
import logging
import threading
from enum import Enum, auto

from Frontend.ASR_module import SpeechRecognizer
from Frontend.communication_client import ClientZeroMQ
from Frontend.config_frontend import BACKEND_IPS, ASR_CONFIDENCE_THRESHOLD, ROBOT_TYPE_KEYS
from Frontend.parsing_module import CodeParser

logger = logging.getLogger("cobot")


class State(Enum):
    """Pipeline execution states."""
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    PARSING = auto()
    EXECUTING = auto()


class Controller:
    """Orchestrates the speech-to-code workflow: IDLE → RECORDING → TRANSCRIBING → PARSING → IDLE."""

    def __init__(self):
        self.state = State.IDLE
        self.asr = SpeechRecognizer()
        self.parser = CodeParser()
        self.gui = None  # Set via set_gui() after GUI is constructed
        self.confidence_threshold: float = ASR_CONFIDENCE_THRESHOLD
        self._cleaned_up: bool = False

        self.recording_active = threading.Event()
        self.recording_thread: threading.Thread | None = None

    def ping(self, robot_type: str) -> None:
        if self.state != State.IDLE:
            return
        robot_key = ROBOT_TYPE_KEYS.get(robot_type, robot_type)
        threading.Thread(target=lambda: self._run_ping(robot_key), daemon=True, name="thread_ping").start()

    def _run_ping(self, robot_key: str) -> None:
        client = ClientZeroMQ(BACKEND_IPS[robot_key])
        success, _ = client.send_command("ping", {})
        client.close()
        status = "ok" if success else "error"
        self.gui.root.after(0, lambda: self.gui.set_connection_status(status))

    def set_gui(self, gui) -> None:
        """Link GUI to controller after construction."""
        self.gui = gui

    def start_recording(self) -> None:
        """Begin audio capture if idle."""
        if self.state != State.IDLE:
            return

        self.state = State.RECORDING
        self.gui.set_gui_status_line("🔴 Recording...", "warning")
        self._set_button_state("warning", True)

        self.recording_active.set()
        self.recording_thread = threading.Thread(
            target=self._recording_loop, daemon=True, name="thread_recording"
        )
        self.recording_thread.start()
        logger.info("Recording started")

    def start_execution(self, robot_type: str) -> None:
        """Stop recording and hand off to the processing pipeline."""
        if self.state != State.RECORDING:
            return

        self.state = State.TRANSCRIBING
        self.gui.set_gui_status_line("Processing...", "info")
        self._set_button_state("info", False)

        self.recording_active.clear()
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
            if self.recording_thread.is_alive():
                logger.warning("Recording thread did not stop within timeout")
            self.recording_thread = None

        logger.info("Recording stopped, starting transcription")

        # Translate display name to backend key once — everything downstream uses the key
        robot_key = ROBOT_TYPE_KEYS.get(robot_type, robot_type)
        threading.Thread(
            target=lambda: self._process_audio(robot_key), daemon=True, name="thread_asr_processing"
        ).start()

    def cleanup(self) -> None:
        """Release all resources on shutdown. Safe to call more than once."""
        if self._cleaned_up:
            return
        self._cleaned_up = True

        self.recording_active.clear()
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
            if self.recording_thread.is_alive():
                logger.warning("Recording thread did not stop within timeout")
        self.recording_thread = None

        self.asr.close()

    def _recording_loop(self) -> None:
        """Capture audio chunks until recording_active is cleared."""
        while self.recording_active.is_set():
            self.asr.read_chunk()

    def _process_audio(self, robot_key: str) -> None:
        """Transcribe captured audio and schedule result display on main thread."""
        audio = self.asr.get_audio()
        result = self.asr.transcribe(audio)
        self.gui.root.after(0, lambda: self._display_transcribe_result(result, robot_key))

    def _display_transcribe_result(self, result: dict, robot_key: str) -> None:
        """Validate transcription result and trigger parsing or fail gracefully."""
        if not result.get("text") or result.get("confidence", 0) == 0:
            self.gui.set_gui_status_line("❌ Transcription failed", "danger")
            self._set_button_state()
            self.state = State.IDLE
            logger.warning("Transcription failed: no text or zero confidence")
            return

        if result.get("confidence", 1) < self.confidence_threshold:
            logger.warning("ASR confidence low: %.2f - parsing may fail", result.get("confidence", 0.0))

        self.state = State.PARSING
        self.gui.set_gui_status_line("Parsing command ...", "info")

        threading.Thread(
            target=lambda: self._parse_command(result["text"], robot_key),
            daemon=True, name="thread_parsing"
        ).start()

    def _parse_command(self, text: str, robot_key: str) -> None:
        """Send transcribed text to the parser and schedule result display on main thread."""
        parse_result = self.parser.parse(text, robot_key)
        self.gui.root.after(0, lambda: self._display_parse_result(parse_result))

    def _display_parse_result(self, parse_result: dict) -> None:
        """Handle parser output — send to backend on success or show error."""
        if parse_result["status"] == "success":
            command_as_string = self._command_to_string(parse_result["command"])
            self.gui.set_gui_status_line("✅ Command parsed — waiting for backend...", "info")
            logger.info("Parser: Command summary \"%s\"", command_as_string)

            self.state = State.EXECUTING
            self._set_button_state("secondary", enabled=False)
            threading.Thread(
                target=self._send_command, args=(parse_result["command"],),
                name="backend-send", daemon=True
            ).start()
        else:
            error = parse_result.get("error", "Unknown parse error")
            self.gui.set_gui_status_line(f"❌ Parse failed: {error}", "danger")
            self.state = State.IDLE
            self._set_button_state()

    def _send_command(self, command: dict) -> None:
        """Serialise and dispatch a parsed command to the backend."""
        data = {
            "mode": "live",
            "robot": command["robot"],
            "commands": command.get("commands", []),
            "message": ""
        }
        logger.info("Client: Sending data to backend")
        logger.debug("Sending data: %s", json.dumps(data)[:500])
        self.client = ClientZeroMQ(BACKEND_IPS[command["robot"]])
        success, response = self.client.send_command("execute_sequence", data)
        self.client.close()
        self.gui.root.after(0, lambda: self._display_execution_result(success, response))

    def _display_execution_result(self, success: bool, response: dict) -> None:
        """Update GUI based on backend response."""
        status = response.get("command")
        data = response.get("data", {})

        if success and status == "success":
            self.gui.set_gui_status_line("✅ Execution complete", "success")
            logger.info("Execution: Backend executed command successfully")
        elif status == "rejected":
            reasons = data.get("reasons") or [data.get("reason", "Unknown reason")]
            for reason in reasons:
                logger.warning("Execution: Command rejected — %s", reason)
            self.gui.set_gui_status_line("❌ Command rejected", "danger")
        else:
            logger.error("Execution: Backend error — %s", data.get("message", response))
            self.gui.set_gui_status_line("❌ Execution failed", "danger")

        self.state = State.IDLE
        self._set_button_state()

    def _command_to_string(self, command: dict) -> str:
        """Convert a parsed command dict to a human-readable summary for logging."""
        commands = command.get("commands", [])
        if not commands:
            return "Empty command"

        parts = []
        for cmd in commands:
            action = cmd.get("action", "unknown")

            if action == "move":
                target = cmd.get("target", {})
                if target.get("type") == "offset_from_current":
                    raw = target.get("offset", {})
                    parts.append(
                        f"Move offset_from_current ({raw.get('x_mm', 0)}, {raw.get('y_mm', 0)}, {raw.get('z_mm', 0)}) mm")
                else:
                    name = target.get("name", target) if isinstance(target, dict) else target
                    parts.append(f"Move to {name} pos.")
            elif action == "gripper":
                state = cmd.get("state") or cmd.get("command", "?")
                parts.append(f"{state.capitalize()} gripper")
            elif action == "pose":
                parts.append(f"{cmd.get('command', '?').capitalize()} pose '{cmd.get('pose_name', '?')}'")
            elif action == "freedrive":
                parts.append(f"Freedrive {'on' if cmd.get('active') else 'off'}")
            elif action == "connection":
                parts.append(f"Connection {cmd.get('command', '?')}")
            elif action == "wait":
                parts.append(f"Wait {cmd.get('duration_s', '?')}s")
            else:
                parts.append(action.capitalize())

        return " → ".join(parts)

    def _set_button_state(self, visual_state: str = "primary", enabled: bool = True) -> None:
        """Update the record button to the given style and enabled state."""
        self.gui.set_button_state("Press and hold to record", visual_state, enabled)