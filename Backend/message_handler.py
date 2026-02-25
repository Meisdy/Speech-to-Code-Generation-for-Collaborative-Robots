from Backend.robot_controllers.base_robot_controller import BaseRobotController
from Backend.robot_controllers.mock_robot_controller import MockRobotController
from typing import Optional # Needed for old py version of ROS / Franka
import logging
import time

logger = logging.getLogger("cobot_backend")

try:
    from Backend.robot_controllers.franka_controller import FrankaController
except ImportError:
    FrankaController = None 

try:
    from Backend.robot_controllers.ur_controller import URController
except ImportError:
    URController = None


class MessageHandler:
    """Processes commands - no knowledge of communication protocol"""

    def __init__(self):
        """Initialize handler - later will include robot controller, logger"""

        self.allowed_commands : list = ['ping', 'get_status', 'execute_sequence']
        self.robot_types : list = ['franka', 'ur', 'mock']  # Supported robot types
        self.robot : Optional[BaseRobotController] = None

    def _load_robot_adapter(self, robot_type: str = "mock") -> dict:
        expected = {"ur": "URController", "franka": "FrankaController", "mock": "MockRobotController"}

        if self.robot and type(self.robot).__name__ == expected[robot_type] and self.robot.is_connected():
            return {"success": True, "message": "Already connected"}

        if self.robot:
            self.robot.disconnect()

        if robot_type == "ur":
            self.robot = URController()
        elif robot_type == "franka":
            if FrankaController is None:
                logger.warning("Could not load franka adapter due to missing franka dependencies")
                return {"success": False, "message": "FrankaController dependencies not installed"}
            self.robot = FrankaController()
        elif robot_type == "mock":
            self.robot = MockRobotController()
        else:
            return {"success": False, "message": f"Unknown robot type: {robot_type}"}

        return self.robot.connect()

    def disconnect_robot(self) -> None:
        """Wraper to disconnect robot"""
        if self.robot:
            self.robot.disconnect()

    def _formatted_response(self, command: str, data: dict) -> dict:
        """Format response as JSON with standard structure."""
        return {
            "command": command,
            "data": data
        }

    def process_message(self, message):
        """
        Process incoming message and return response.

        Args:
            message: dict with {"command": str, "data": dict}

        Returns:
            dict with {"command": str, "data": dict}
        """
        try:
            command = message.get("command", "")
            data = message.get("data", {})

            if command not in self.allowed_commands:
                return self._unknown_command(command)

            commands = {
                "ping": self._answer_ping,
                "get_status": self._send_status,
                "execute_sequence": lambda: self._execute_sequence(data),
            }

            return commands[command]()

        except Exception as e:
            logger.error(f'Error occured while processing message: {e}')
            return self._formatted_response('error', {"error message": str(e)})

    def _answer_ping(self) -> dict:
        """Handle ping command"""
        return self._formatted_response('success', {'message': 'Backend Alive'})

    def _unknown_command(self, command):
        """Handle unknown commands"""
        return self._formatted_response('rejected', {"reason": f"Unknown command: {command}"})

    def _send_status(self):
        """Handle get_status command"""
        return self._formatted_response('success', {"Connected Robots": 'unknown' })

    def _execute_sequence(self, data):
        robot_type = data['robot']
        if robot_type not in self.robot_types:
            return self._formatted_response('rejected', {"reason": f"Unsupported robot type: {robot_type}"})

        result = self._load_robot_adapter(robot_type)
        if not result["success"]:
            return self._formatted_response('rejected', {"reason": f"Could not connect to {robot_type}: {result['message']}"})

        responses = [self._process_command(cmd, self.robot) for cmd in data.get('commands', [])]
        return self._formatted_response('success', {'responses': responses})

    def _process_command(self, command: dict, robot: BaseRobotController) -> dict:
        """
        Process a single command

        Args:
            command: dict with the command details
            robot: MockRobotController instance

        Returns:
            dict with the result of the command execution
        """
        action = command.get('action', '')

        if action == "move":
            motion_type = command["motion_type"]
            target = command["target"]
            pose_name = target["name"]
            speed = command.get("speed")

            pose = robot.get_pose(pose_name)
            if pose is None:
                return {"success": False, "message": f"Unknown pose {pose_name}"}

            offset = None
            if target.get("type") == "offset_from_pose":
                raw = target["offset"]
                offset = [raw["x_mm"], raw["y_mm"], raw["z_mm"]]

            if motion_type == "moveJ":
                return robot.move_joint(pose, speed, offset)
            else:
                return robot.move_linear(pose, speed, offset)


        elif action == 'gripper':
            gripper_operation = command['command']
            if gripper_operation == 'open':
                response = robot.gripper_open()
            elif gripper_operation == 'close':
                response = robot.gripper_close()
            else:
                return {"error": f"Unknown gripper command: {gripper_operation}"}
            return response

        elif action == 'wait':
            time.sleep(command['duration_s'])
            return {"message": f"Waited for {command['duration_s']} seconds"}

        elif action == 'pose':
            mode = command['command']
            pose_name = command['pose_name']
            overwrite = command.get('overwrite', False)

            if mode == 'teach':
                return robot.save_pose(pose_name, overwrite)
            elif mode == 'delete':
                return robot.delete_pose(pose_name)
            else:
                return {"error": f"Unknown pose management mode: {mode}"}

        else:
            return {"error": f"Unknown action: {action}"}






