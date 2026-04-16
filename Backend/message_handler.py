import importlib
import inspect
import logging
import time
import threading
from typing import Dict, Optional, Type, Tuple

from Backend.robot_controllers.base_robot_controller import BaseRobotController
from Backend.config_backend import AVAILABLE_ROBOTS, ALLOWED_COMMANDS

logger = logging.getLogger("cobot_backend")


def _load_controllers() -> Dict[str, Type[BaseRobotController]]:
    """Import controller adapters listed in config, skipping any that fail to load."""
    controllers = {}
    for robot_type in AVAILABLE_ROBOTS:
        module_name = f"Backend.robot_controllers.{robot_type}_controller"
        try:
            module = importlib.import_module(module_name)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseRobotController) and obj is not BaseRobotController:
                    controllers[robot_type] = obj
                    break
        except ImportError as e:
            logger.info("Controller '%s' from config not available: %s", robot_type, e)
    return controllers


CONTROLLERS: Dict[str, Type[BaseRobotController]] = _load_controllers()


class MessageHandler:
    """Processes incoming commands and dispatches them to the robot controller."""

    def __init__(self) -> None:
        self.robot: Optional[BaseRobotController] = None
        self._script_stop_event: threading.Event = threading.Event()
        self._script_thread: Optional[threading.Thread] = None

        for robot_type, cls in CONTROLLERS.items():
            logger.debug("Controller available: '%s' -> %s", robot_type, cls.__name__)

    def disconnect_robot(self) -> None:
        """Disconnect and release the current robot controller."""
        if self.robot:
            try:
                self.robot.disconnect()
            except Exception as e:
                logger.error("Error during robot disconnect: %s", e)
            self.robot = None

    def process_message(self, message: dict) -> dict:
        """Parse and dispatch an incoming command message."""
        try:
            command = message.get("command", "")
            data = message.get("data", {})

            if command not in ALLOWED_COMMANDS:
                return self._unknown_command(command)

            commands = {
                "ping": self._answer_ping,
                "execute_sequence": lambda: self._execute_sequence(data),
                "save_script": lambda: self._save_script(data),
                "run_script": lambda: self._run_script(data),
                "stop_script": self._stop_script,
                "get_script_status": self._get_script_status,
                "delete_script": lambda: self._delete_script(data),
            }

            return commands[command]()

        except Exception as e:
            logger.exception("Error processing message: %s", message)
            return self._formatted_response("error", {"error message": str(e)})



    def _ensure_robot_ready(self, robot_type: str) -> dict:
        self._current_robot_type = robot_type
        expected_class = CONTROLLERS[robot_type]

        # Already the right robot and fully ready — nothing to do
        if self.robot and type(self.robot) is expected_class:
            if self.robot.is_ready():
                return {"success": True, "message": "Ready"}
            # Right robot, wrong state — try to recover without full reconnect
            if self.robot.is_connected():
                return self.robot.activate_robot()
            # Socket is dead — fall through to full reconnect

        # Wrong robot or dead connection — full reload
        if self.robot:
            self.robot.disconnect()

        self.robot = expected_class() # Arg warning can be ignored. A controller should always declare a fixed pos file

        result = self.robot.connect()
        if not result["success"]:
            logger.warning("Could not connect to %s: %s", robot_type, result["message"])
            return result

        result = self.robot.activate_robot()  # No-op for controllers that handle activation internally
        if not result["success"]:
            logger.error("Failed to activate %s: %s", robot_type, result["message"])
            return result

        return result

    def _is_script_robot_supported(self, robot_type: str) -> Tuple[bool, dict]:
        """Check if robot type is supported for script operations.

        Returns (True, {}) if supported, (False, error_response) otherwise.
        """
        if not robot_type or robot_type not in CONTROLLERS:
            return False, self._formatted_response("rejected", {"message": f"Unsupported robot type: {robot_type}"})
        return True, {}

    def _formatted_response(self, command: str, data: dict) -> dict:
        return {"command": command, "data": data}

    def _answer_ping(self) -> dict:
        return self._formatted_response("success", {"message": "Backend Alive"})

    def _unknown_command(self, command: str) -> dict:
        return self._formatted_response("rejected", {"reason": f"Unknown command: {command}"})

    def _execute_sequence(self, data: dict) -> dict:
        robot_type = data["robot"]
        if robot_type not in CONTROLLERS:
            return self._formatted_response("rejected", {"reason": f"Unsupported robot type: {robot_type}"})

        result = self._ensure_robot_ready(robot_type)
        if not result["success"]:
            return self._formatted_response("rejected", {"reason": f"Could not connect to {robot_type}: {result['message']}"})

        commands = data.get("commands", [])

        validation_errors = [
            error
            for cmd in commands
            if (error := self._validate_command(cmd, self.robot)) is not None
        ]
        if validation_errors:
            logger.warning("Sequence rejected due to %d validation error(s)", len(validation_errors))
            return self._formatted_response("rejected", {"reasons": validation_errors})

        for cmd in commands:
            result = self._process_command(cmd, self.robot)
            if not result["success"]:
                logger.error("Sequence aborted at runtime: %s", result["message"])
                return self._formatted_response("error", {"message": result["message"]})

        return self._formatted_response("success", {"message": f"Sequence of {len(commands)} command(s) completed"})

    def _validate_command(self, command: dict, robot: BaseRobotController) -> Optional[str]:
        """Check a command for errors without executing it. Returns an error string or None.

        Structural validation is handled by the parser. This only checks runtime state
        that the frontend cannot know — specifically whether named poses exist on the robot.
        """
        if command.get("action") == "move":
            target = command.get("target", {})
            if target.get("type") == "offset_from_current":
                return None  # No pose lookup needed — position resolved at execution time
            pose_name = target.get("name")
            if robot.get_pose(pose_name) is None:
                return f"Unknown pose: '{pose_name}'"
        return None

    def _process_command(self, command: dict, robot: BaseRobotController) -> dict:
        """Dispatch a single command to the appropriate robot method."""
        action = command.get("action", "")

        if action == "move":
            motion_type = command["motion_type"]
            target = command["target"]
            speed = command.get("speed")

            if target.get("type") == "offset_from_current":
                state = robot.get_current_pose()
                if not state.get("success"):
                    return {"success": False, "message": f"Could not read current pose: {state.get('message', 'unknown error')}"}

                raw = target["offset"]
                offset = [raw.get("x_mm", 0.0), raw.get("y_mm", 0.0), raw.get("z_mm", 0.0)]

                current_pose = {
                    "name": "current",
                    "pos": state["pose"][:3],
                    "quat": state["pose"][3:],
                    "joints": state.get("joint_positions", [])
                }
                logger.info("offset_from_current resolved from pos %s", current_pose["pos"])
                return robot.move_linear(current_pose, speed, offset)

            pose_name = target["name"]
            pose = robot.get_pose(pose_name)

            offset = None
            if target.get("type") == "offset_from_pose":
                raw = target.get("offset", {})
                offset = [raw.get("x_mm", 0.0), raw.get("y_mm", 0.0), raw.get("z_mm", 0.0)]

            if motion_type == "moveJ":
                return robot.move_joint(pose, speed, offset)
            else:
                return robot.move_linear(pose, speed, offset)

        elif action == "gripper":
            gripper_operation = command["command"]
            if gripper_operation == "open":
                return robot.gripper_open()
            else:
                return robot.gripper_close()

        elif action == "wait":
            logger.info("Waiting for %is", command["duration_s"])
            time.sleep(command["duration_s"])
            return {"success": True, "message": f"Waited for {command['duration_s']} seconds"}

        elif action == "pose":
            mode = command["command"]
            pose_name = command["pose_name"]

            if mode == "teach":
                return robot.save_pose(pose_name)
            else:
                return robot.delete_pose(pose_name)

        elif action == "freedrive":
            if command["active"]:
                return robot.enable_freedrive()
            else:
                return robot.disable_freedrive()

        elif action == "connection":
            if command["command"] == "disconnect":
                self.disconnect_robot()
                return {"success": True, "message": "Robot disconnected"}
            else:
                return self._ensure_robot_ready(self._current_robot_type)

        else:
            return {"success": False, "message": f"Unknown action: {action}"}

    def _save_script(self, data: dict) -> dict:
        robot_type = data.get("robot")
        script_name = data.get("script_name")
        commands = data.get("commands", [])

        supported, response = self._is_script_robot_supported(robot_type)
        if not supported:
            return response
        if not script_name or not isinstance(commands, list):
            return self._formatted_response("rejected", {"message": "Missing script_name or commands"})

        result = self._ensure_robot_ready(robot_type) # This could be handled differently to save on execution time
        if not result["success"]:
            return self._formatted_response("rejected", {"message": f"Could not connect to {robot_type}: {result['message']}"})

        result = self.robot.save_script(script_name, commands)
        if not result["success"]:
            return self._formatted_response("error", {"message": result["message"]})

        logger.info("Script '%s' saved for robot '%s' with %d command(s)", script_name, robot_type, len(commands))
        return self._formatted_response("success", {"message": f"Script '{script_name}' saved"})

    def _run_script(self, data: dict) -> dict:
        robot_type = data.get("robot")
        script_name = data.get("script_name")
        loop = data.get("loop", 1)

        supported, response = self._is_script_robot_supported(robot_type)
        if not supported:
            return response

        result = self._ensure_robot_ready(robot_type)
        if not result["success"]:
            return self._formatted_response("rejected", {"message": f"Could not connect to {robot_type}: {result['message']}"})

        script = self.robot.get_script(script_name)
        if script is None:
            return self._formatted_response("rejected", {"message": f"Unknown script: '{script_name}'"})

        if self._script_thread and self._script_thread.is_alive():
            return self._formatted_response("rejected", {"message": "A script is already running"})

        validation_errors = [
            error
            for cmd in script
            if (error := self._validate_command(cmd, self.robot)) is not None
        ]
        if validation_errors:
            logger.warning("Script '%s' rejected: %s", script_name, validation_errors)
            return self._formatted_response("rejected", {"reasons": validation_errors})

        self._script_stop_event.clear()
        self._script_thread = threading.Thread(
            target=self._run_script_loop,
            args=(script_name, loop, script),
            daemon=True,
            name="thread_script_loop"
        )
        self._script_thread.start()
        logger.info("Script '%s' started for robot '%s', loop=%d", script_name, robot_type, loop)
        return self._formatted_response("success", {"message": f"Script '{script_name}' started"})

    def _stop_script(self) -> dict:
        """Signal the running script loop to stop after the current command."""
        self._script_stop_event.set()
        logger.info("Stop signal sent to script loop")
        return self._formatted_response("success", {"message": "Stop signal sent"})

    def _run_script_loop(self, script_name: str, loop: int, commands: list) -> None:
        """Execute script commands in a loop. Checks stop event between commands."""
        iteration = 0
        while not self._script_stop_event.is_set():
            logger.info("Script '%s' — iteration %d", script_name, iteration + 1)
            for cmd in commands:
                if self._script_stop_event.is_set():
                    break
                result = self._process_command(cmd, self.robot)
                if not result["success"]:
                    logger.error("Script '%s' aborted at command: %s", script_name, result["message"])
                    return

            iteration += 1
            if loop != -1 and iteration >= loop:
                break

        logger.info("Script '%s' finished after %d iteration(s)", script_name, iteration)

    def _get_script_status(self) -> dict:
        is_running = self._script_thread is not None and self._script_thread.is_alive()
        return self._formatted_response("success", {"is_running": is_running})

    def _delete_script(self, data: dict) -> dict:
        robot_type = data.get("robot")
        script_name = data.get("script_name")

        supported, response = self._is_script_robot_supported(robot_type)
        if not supported:
            return response

        result = self._ensure_robot_ready(robot_type)
        if not result["success"]:
            return self._formatted_response("rejected", {"message": f"Could not connect to {robot_type}: {result['message']}"})

        result = self.robot.delete_script(script_name)
        if not result["success"]:
            return self._formatted_response("error", {"message": result["message"]})

        logger.info("Script '%s' deleted", script_name)
        return self._formatted_response("success", {"message": f"Script '{script_name}' deleted"})