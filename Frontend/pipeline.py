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
    SCRIPT_RECORDING = auto()
    SCRIPT_CONFIRMING = auto()
    SCRIPT_RUNNING = auto()


class Controller:
    """Orchestrates the speech-to-code workflow: IDLE → RECORDING → TRANSCRIBING → PARSING → IDLE."""

    def __init__(self):
        self.state = State.IDLE
        self.asr = SpeechRecognizer()
        self.parser = CodeParser()
        self.gui = None  # Set via set_gui() after GUI is constructed
        self.confidence_threshold: float = ASR_CONFIDENCE_THRESHOLD
        self._cleaned_up: bool = False
        self._script_name: str | None = None
        self._script_buffer: list | None = None
        self._active_robot_key: str | None = None
        self._edit_index: int | None = None

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
        """Begin audio capture if idle, in script recording, or in script confirming (for step edit)."""
        if self.state not in (State.IDLE, State.SCRIPT_RECORDING, State.SCRIPT_CONFIRMING):
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

        robot_key = ROBOT_TYPE_KEYS.get(robot_type, robot_type)
        threading.Thread(
            target=lambda: self._process_audio(robot_key), daemon=True, name="thread_asr_processing"
        ).start()

    def confirm_script(self, robot_type: str) -> None:
        """Send buffered script to backend for storage. Called by GUI Confirm button."""
        if self.state != State.SCRIPT_CONFIRMING:
            return

        robot_key = ROBOT_TYPE_KEYS.get(robot_type, robot_type)
        data = {
            "script_name": self._script_name,
            "commands": self._script_buffer
        }
        logger.info("Saving script '%s' with %d command(s)", self._script_name, len(self._script_buffer))
        self._set_button_state("secondary", enabled=False)
        self.gui.hide_confirmation_panel()

        threading.Thread(
            target=lambda: self._send_save_script(robot_key, data),
            daemon=True, name="thread_save_script"
        ).start()

    def discard_script(self) -> None:
        """Discard buffered script and return to idle. Called by GUI Cancel button."""
        if self.state != State.SCRIPT_CONFIRMING:
            return

        logger.info("Script '%s' discarded", self._script_name)
        self._script_name = None
        self._script_buffer = None
        self._edit_index = None
        self.gui.hide_confirmation_panel()
        self.gui.set_gui_status_line("Script discarded", "secondary")
        self.state = State.IDLE
        self._set_button_state()

    def stop_script(self, robot_type: str) -> None:
        """Send stop signal to backend. Called by GUI Stop button."""
        if self.state != State.SCRIPT_RUNNING:
            return

        robot_key = ROBOT_TYPE_KEYS.get(robot_type, robot_type)
        threading.Thread(
            target=lambda: self._send_stop_script(robot_key),
            daemon=True, name="thread_stop_script"
        ).start()

    def select_step_for_edit(self, index: int) -> None:
        """Mark a script step for replacement. Called by GUI edit button."""
        if self.state != State.SCRIPT_CONFIRMING:
            return
        self._edit_index = index
        self.gui.set_gui_status_line(f"🔄 Hold button to re-record step {index + 1}", "warning")

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
            self._restore_state_after_failure()
            logger.warning("Transcription failed: no text or zero confidence")
            return

        if result.get("confidence", 1) < self.confidence_threshold:
            logger.warning("ASR confidence low: %.2f - parsing may fail", result.get("confidence", 0.0))

        self.state = State.PARSING
        self.gui.set_gui_status_line("Parsing command...", "info")

        threading.Thread(
            target=lambda: self._parse_command(result["text"], robot_key),
            daemon=True, name="thread_parsing"
        ).start()

    def _parse_command(self, text: str, robot_key: str) -> None:
        """Send transcribed text to the parser and schedule result display on main thread."""
        parse_result = self.parser.parse(text, robot_key)
        self.gui.root.after(0, lambda: self._display_parse_result(parse_result))

    def _display_parse_result(self, parse_result: dict) -> None:
        """Route a successful parse result to the correct handler."""
        if parse_result["status"] != "success":
            error = parse_result.get("error", "Unknown parse error")
            self.gui.set_gui_status_line(f"❌ Parse failed: {error}", "danger")
            self._restore_state_after_failure()
            return

        command = parse_result["command"]
        logger.info("Parser: Command summary \"%s\"", self._command_to_string(command))

        first_cmd = command.get("commands", [{}])[0]

        if self._edit_index is not None:
            self._handle_step_replacement(command.get("commands", []))
        elif first_cmd.get("action") == "script":
            self._handle_script_command(first_cmd, command.get("robot"))
        elif self._script_buffer is not None:
            self._handle_script_buffer(command.get("commands", []))
        else:
            self._handle_live_command(command)

    def _handle_script_command(self, cmd: dict, robot_key: str) -> None:
        """Handle script meta-commands: start, save, run, stop."""
        script_cmd = cmd.get("command")

        if script_cmd == "start":
            self._script_name = cmd.get("script_name", "unnamed_script")
            self._script_buffer = []
            self.state = State.SCRIPT_RECORDING
            self.gui.set_gui_status_line(f"📝 Recording script '{self._script_name}' — issue commands", "warning")
            self._set_button_state("warning", True)
            logger.info("Script recording started: '%s'", self._script_name)

        elif script_cmd == "save":
            name_from_save = cmd.get("script_name")
            if name_from_save and name_from_save != "unnamed_script":
                self._script_name = name_from_save
            if not self._script_buffer:
                self.gui.set_gui_status_line("❌ Script is empty — nothing to save", "danger")
                self.state = State.SCRIPT_RECORDING
                self._set_button_state("warning", True)
                return
            steps = [self._format_cmd(c) for c in self._script_buffer]
            self.state = State.SCRIPT_CONFIRMING
            self.gui.show_confirmation_panel(self._script_name, steps, on_edit=self.select_step_for_edit)
            self._set_button_state("primary", False)
            logger.info("Script '%s' ready for confirmation, %d command(s)", self._script_name,
                        len(self._script_buffer))

        elif script_cmd == "run":
            script_name = cmd.get("script_name")
            loop = cmd.get("loop", 1)
            self._active_robot_key = robot_key
            self.state = State.SCRIPT_RUNNING
            self.gui.set_gui_status_line(f"▶ Running script '{script_name}'...", "info")
            self.gui.show_stop_button()
            self._set_button_state("secondary", enabled=False)
            threading.Thread(
                target=lambda: self._send_run_script(robot_key, script_name, loop),
                daemon=True, name="thread_run_script"
            ).start()

        elif script_cmd == "stop":
            if self.state == State.SCRIPT_RUNNING:
                threading.Thread(
                    target=lambda: self._send_stop_script(robot_key),
                    daemon=True, name="thread_stop_script"
                ).start()
            else:
                logger.info("Script '%s' cancelled by voice", self._script_name)
                self._script_name = None
                self._script_buffer = None
                self._edit_index = None
                self.gui.set_gui_status_line("Script cancelled", "secondary")
                self.state = State.IDLE
                self._set_button_state()

    def _handle_script_buffer(self, commands: list) -> None:
        """Append parsed commands to the active script buffer."""
        self._script_buffer.extend(commands)
        count = len(self._script_buffer)
        logger.info("Script buffer: added %d command(s), total %d", len(commands), count)
        self.gui.set_gui_status_line(f"📝 Script '{self._script_name}' — {count} command(s) recorded", "warning")
        self.state = State.SCRIPT_RECORDING
        self._set_button_state("warning", True)

    def _handle_step_replacement(self, commands: list) -> None:
        """Replace the selected step in the buffer and refresh the confirmation panel."""
        self._script_buffer[self._edit_index:self._edit_index + 1] = commands
        self._edit_index = None
        steps = [self._format_cmd(c) for c in self._script_buffer]
        self.gui.show_confirmation_panel(self._script_name, steps, on_edit=self.select_step_for_edit)
        self.gui.set_gui_status_line("✅ Step replaced — review and confirm", "info")
        self.state = State.SCRIPT_CONFIRMING
        self._set_button_state("primary", False)

    def _handle_live_command(self, command: dict) -> None:
        """Dispatch a parsed command to the backend for immediate execution."""
        self.gui.set_gui_status_line("✅ Command parsed — waiting for backend...", "info")
        self.state = State.EXECUTING
        self._set_button_state("secondary", enabled=False)
        threading.Thread(
            target=self._send_command, args=(command,),
            name="backend-send", daemon=True
        ).start()

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

    def _send_save_script(self, robot_key: str, data: dict) -> None:
        """Send save_script command to backend."""
        data["robot"] = robot_key
        client = ClientZeroMQ(BACKEND_IPS[robot_key])
        success, response = client.send_command("save_script", data)
        client.close()
        self.gui.root.after(0, lambda: self._display_save_result(success, response))

    def _send_run_script(self, robot_key: str, script_name: str, loop: int) -> None:
        """Send run_script command to backend."""
        data = {"script_name": script_name, "loop": loop, "robot": robot_key}
        client = ClientZeroMQ(BACKEND_IPS[robot_key])
        success, response = client.send_command("run_script", data)
        client.close()
        self.gui.root.after(0, lambda: self._display_run_result(success, response))

    def _send_stop_script(self, robot_key: str) -> None:
        """Send stop_script command to backend."""
        client = ClientZeroMQ(BACKEND_IPS[robot_key])
        success, response = client.send_command("stop_script", {})
        client.close()
        self.gui.root.after(0, lambda: self._display_stop_result(success, response))

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

    def _display_save_result(self, success: bool, response: dict) -> None:
        """Update GUI after script save attempt."""
        if success and response.get("command") == "success":
            self.gui.set_gui_status_line(f"✅ Script '{self._script_name}' saved", "success")
            logger.info("Script '%s' saved successfully", self._script_name)
        else:
            error = response.get("data", {}).get("message", "Unknown error")
            self.gui.set_gui_status_line(f"❌ Save failed: {error}", "danger")
            logger.error("Script save failed: %s", error)

        self._script_name = None
        self._script_buffer = None
        self.state = State.IDLE
        self._set_button_state()

    def _display_run_result(self, success: bool, response: dict) -> None:
        """Update GUI after run_script dispatch. Backend responds immediately."""
        if success and response.get("command") == "success":
            self.gui.set_gui_status_line("▶ Script running", "success")
            logger.info("Script dispatched successfully")
            self.gui.root.after(2000, self._poll_script_status)
        else:
            error = response.get("data", {}).get("message", "Unknown error")
            self.gui.set_gui_status_line(f"❌ Run failed: {error}", "danger")
            logger.error("Script run failed: %s", error)
            self.gui.hide_stop_button()
            self.state = State.IDLE
            self._set_button_state()

    def _display_stop_result(self, success: bool, response: dict) -> None:
        """Update GUI after stop_script dispatch."""
        if success:
            self.gui.set_gui_status_line("⏹ Stop signal sent", "secondary")
            logger.info("Stop signal sent to backend")
        else:
            self.gui.set_gui_status_line("❌ Stop failed", "danger")
            logger.error("Stop script failed: %s", response)

        self.gui.hide_stop_button()
        self.state = State.IDLE
        self._set_button_state()

    def _poll_script_status(self) -> None:
        """Schedule a background status check if script is still marked as running."""
        if self.state != State.SCRIPT_RUNNING:
            return
        threading.Thread(
            target=self._fetch_script_status,
            daemon=True, name="thread_poll_status"
        ).start()

    def _fetch_script_status(self) -> None:
        """Query backend for script thread status."""
        client = ClientZeroMQ(BACKEND_IPS[self._active_robot_key])
        success, response = client.send_command("get_script_status", {})
        client.close()
        self.gui.root.after(0, lambda: self._handle_script_status(success, response))

    def _handle_script_status(self, success: bool, response: dict) -> None:
        """React to script status response — continue polling or reset to idle."""
        if not success:
            self.gui.hide_stop_button()
            self.gui.set_gui_status_line("❌ Lost connection to backend", "danger")
            self._active_robot_key = None
            self.state = State.IDLE
            self._set_button_state()
            return

        is_running = response.get("data", {}).get("is_running", False)
        if is_running:
            self.gui.root.after(2000, self._poll_script_status)
        else:
            self.gui.hide_stop_button()
            self.gui.set_gui_status_line("✅ Script finished", "success")
            logger.info("Script completed")
            self._active_robot_key = None
            self.state = State.IDLE
            self._set_button_state()

    def _restore_state_after_failure(self) -> None:
        """Return to the correct state after a transcription or parse failure."""
        if self._edit_index is not None:
            self._edit_index = None
            self.state = State.SCRIPT_CONFIRMING
            self._set_button_state("primary", False)
        elif self._script_buffer is not None:
            self.state = State.SCRIPT_RECORDING
            self._set_button_state("warning", True)
        else:
            self.state = State.IDLE
            self._set_button_state()

    def _command_to_string(self, command: dict) -> str:
        """Convert a parsed command dict to a human-readable summary for logging."""
        commands = command.get("commands", [])
        if not commands:
            return "Empty command"
        return " → ".join(self._format_cmd(cmd) for cmd in commands)

    def _format_cmd(self, cmd: dict) -> str:
        """Format a single command dict into a human-readable string."""
        action = cmd.get("action", "unknown")
        if action == "move":
            target = cmd.get("target", {})
            motion_type = cmd.get("motion_type", "moveJ")
            if target.get("type") == "offset_from_current":
                raw = target.get("offset", {})
                return f"{motion_type} offset_from_current ({raw.get('x_mm', 0)}, {raw.get('y_mm', 0)}, {raw.get('z_mm', 0)}) mm"
            name = target.get("name", target) if isinstance(target, dict) else target
            return f"{motion_type} to {name}"
        elif action == "gripper":
            state = cmd.get("state") or cmd.get("command", "?")
            return f"{state.capitalize()} gripper"
        elif action == "pose":
            return f"{cmd.get('command', '?').capitalize()} pose '{cmd.get('pose_name', '?')}'"
        elif action == "freedrive":
            return f"Freedrive {'on' if cmd.get('active') else 'off'}"
        elif action == "connection":
            return f"Connection {cmd.get('command', '?')}"
        elif action == "wait":
            return f"Wait {cmd.get('duration_s', '?')}s"
        elif action == "script":
            sc = cmd.get("command", "?")
            name = cmd.get("script_name", "?")
            loop = cmd.get("loop", 1)
            return f"Script {sc} '{name}'" + (f" x{loop}" if sc == "run" else "")
        return action.capitalize()

    def _set_button_state(self, visual_state: str = "primary", enabled: bool = True) -> None:
        """Update the record button to the given style and enabled state."""
        self.gui.set_button_state("Press and hold to record", visual_state, enabled)