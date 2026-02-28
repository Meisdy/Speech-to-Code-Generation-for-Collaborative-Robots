import logging
import time
from typing import Optional

from Backend.robot_controllers.base_robot_controller import BaseRobotController
from Backend.robot_controllers.mock_robot_controller import MockRobotController

try:
    from Backend.robot_controllers.franka_controller import FrankaController
except ImportError:
    FrankaController = None

try:
    from Backend.robot_controllers.ur_controller import URController
except ImportError:
    URController = None

logger = logging.getLogger("cobot_backend")


class MessageHandler:
    """Processes incoming commands and dispatches them to the robot controller."""

    ALLOWED_COMMANDS = ["ping", "get_status", "execute_sequence"]
    ROBOT_TYPES = ["franka", "ur", "mock"]

    def __init__(self):
        self.robot: Optional[BaseRobotController] = None

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
        expected = {"ur": "URController", "franka": "FrankaController", "mock": "MockRobotController"}

        # Already the right robot and fully ready — nothing to do
        if self.robot and type(self.robot).__name__ == expected[robot_type]:
            if self.robot.is_ready():
                return {"success": True, "message": "Ready"}
            # Right robot, wrong state — try to recover without full reconnect
            if self.robot.is_connected():
                return self.robot.activate_robot()
            # Socket is dead — fall through to full reconnect

        # Wrong robot or dead connection — full reload
        if self.robot:
            self.robot.disconnect()

        if robot_type == "ur":
            self.robot = URController()
        elif robot_type == "franka":
            if FrankaController is None:
                logger.warning("Cannot load Franka adapter: dependencies not installed")
                return {"success": False, "message": "FrankaController dependencies not installed"}
            self.robot = FrankaController()
        elif robot_type == "mock":
            self.robot = MockRobotController()
        else:
            return {"success": False, "message": f"Unknown robot type: {robot_type}"}

        result = self.robot.connect()
        if not result["success"]:
            logger.warning("Could not connect to %s: %s", robot_type, result["message"])
            return result

        result = self.robot.activate_robot()  # This will be passed automatically if robot has no defined activation
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
        if robot_type not in self.ROBOT_TYPES:
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