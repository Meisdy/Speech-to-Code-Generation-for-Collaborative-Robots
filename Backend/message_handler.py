from .robot_controllers.base_robot_controller import BaseRobotController
from .robot_controllers.mock_robot_controller import MockRobotController

try:
    from .robot_controllers.franka_controller import FrankaController
except ImportError:
    FrankaController = None

try:
    from .robot_controllers.ur_controller import URController

except ImportError:
    URController = None

import time

class MessageHandler:
    """Processes commands - no knowledge of communication protocol"""

    def __init__(self):
        """Initialize handler - later will include robot controller, logger"""

        self.allowed_commands : list = ['ping', 'get_status', 'execute_sequence']
        self.robot_types : list = ['franka', 'ur', 'mock']  # Supported robot types
        self.robot = None

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
                return {
                    "success": False,
                    "message": "FrankaController dependencies not installed"
                }
            self.robot = FrankaController()
        elif robot_type == "mock":
            self.robot = MockRobotController()

        return self.robot.connect()

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

            if command == "ping":
                return self._answer_ping()
            elif command == "get_status":
                return self._send_status()
            elif command == "execute_sequence":
                return self._execute_sequence(data)


        except Exception as e:
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
            motion_type = command.get('motion_type', 'moveJ')
            pose_name = command['target']['name']
            offset = command.get('offset')
            speed = command.get('speed')

            entry = robot.get_pose(pose_name)
            if entry is None:
                return {"success": False, "message": f"Unknown pose: {pose_name}"}

            if motion_type == 'moveJ':
                return robot.move_joint(entry, speed, offset)
            else:
                return robot.move_linear(entry, speed, offset)
        elif action == "gripper":
            gripper_operation = command['command']
            if gripper_operation == "open":
                return robot.gripper_open()
            elif gripper_operation == "close":
                return robot.gripper_close()
            else:
                return {"error": f"Unknown gripper command: {gripper_operation}"}

        elif action == "wait":
            duration_s = command.get('duration_s', 1.0)
            time.sleep(duration_s)
            return {"message": f"Waited for {duration_s} seconds"}
        
        elif action == "pose":
            mode = command['command']
            pose_name = command['pose_name']
            overwrite = command.get('overwrite', False)

            if mode == "teach":
                return robot.save_pose(pose_name, overwrite)
            elif mode == "delete":
                return robot.delete_pose(pose_name)
            else:
                return {"error": f"Unknown pose management mode: {mode}"}
        else:
            return {"error": f"Unknown action: {action}"}






