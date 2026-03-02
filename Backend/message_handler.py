import importlib
import inspect
import logging
import time
from typing import Dict, Optional, Type

from Backend.robot_controllers.base_robot_controller import BaseRobotController
from Backend.config_backend import AVAILABLE_ROBOTS

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

    ALLOWED_COMMANDS = ["ping", "get_status", "execute_sequence"]

    def __init__(self):
        self.robot: Optional[BaseRobotController] = None
        for robot_type, cls in CONTROLLERS.items():
            logger.debug("Controller available: '%s' -> %s", robot_type, cls.__name__)

    def disconnect_robot(self) -> None:
        """Disconnect and release the current robot controller."""
        if self.robot:
            if self.robot.is_connected():
                self.robot.disconnect()
            self.robot = None

    def process_message(self, message: dict) -> dict:
        """Parse and dispatch an incoming command message."""
        try:
            command = message.get("command", "")
            data = message.get("data", {})

            if command not in self.ALLOWED_COMMANDS:
                return self._unknown_command(command)

            commands = {
                "ping": self._answer_ping,
                "get_status": self._send_status,
                "execute_sequence": lambda: self._execute_sequence(data),
            }

            return commands[command]()

        except Exception as e:
            logger.exception("Error processing message: %s", message)
            return self._formatted_response("error", {"error message": str(e)})

    def _ensure_robot_ready(self, robot_type: str) -> dict:
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

        self.robot = expected_class()

        result = self.robot.connect()
        if not result["success"]:
            logger.warning("Could not connect to %s: %s", robot_type, result["message"])
            return result

        result = self.robot.activate_robot()  # No-op for controllers that handle activation internally
        if not result["success"]:
            logger.error("Failed to activate %s: %s", robot_type, result["message"])
            return result

        return result

    def _formatted_response(self, command: str, data: dict) -> dict:
        return {"command": command, "data": data}

    def _answer_ping(self) -> dict:
        return self._formatted_response("success", {"message": "Backend Alive"})

    def _unknown_command(self, command: str) -> dict:
        return self._formatted_response("rejected", {"reason": f"Unknown command: {command}"})

    def _send_status(self) -> dict:
        return self._formatted_response("success", {"Connected Robots": "unknown"})

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
            pose_name = command.get("target", {}).get("name")
            if robot.get_pose(pose_name) is None:
                return f"Unknown pose: '{pose_name}'"
        return None

    def _process_command(self, command: dict, robot: BaseRobotController) -> dict:
        """Dispatch a single command to the appropriate robot method."""
        action = command.get("action", "")

        if action == "move":
            motion_type = command["motion_type"]
            target = command["target"]
            pose_name = target["name"]
            speed = command.get("speed")

            pose = robot.get_pose(pose_name)

            offset = None
            if target.get("type") == "offset_from_pose":
                raw = target["offset"]
                offset = [raw["x_mm"], raw["y_mm"], raw["z_mm"]]

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
            overwrite = command.get("overwrite", False)

            if mode == "teach":
                return robot.save_pose(pose_name, overwrite)
            else:
                return robot.delete_pose(pose_name)

        elif action == "freedrive":
            if command["active"]:
                return robot.enable_freedrive()
            else:
                return robot.disable_freedrive()
        else:
            return {"success": False, "message": f"Unknown action: {action}"}