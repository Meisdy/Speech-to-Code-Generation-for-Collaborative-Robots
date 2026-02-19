from Backend.robot_controllers.base_robot_controller import BaseRobotController
from Backend.robot_controllers.mock_robot_controller import MockRobotController
from Backend.robot_controllers.franka_controller import FrankaController
from Backend.robot_controllers.ur_controller import URController
import time

class MessageHandler:
    """Processes commands - no knowledge of communication protocol"""

    def __init__(self):
        """Initialize handler - later will include robot controller, logger"""

        self.allowed_commands = ['ping', 'get_status', 'execute_sequence']
        self.robot_types = ['franka', 'ur', 'mock']  # Supported robot types
        self.robots = self._initialize_robots(config={})  # Placeholder for config

    def _initialize_robots(self, config):
        robots = {}
        candidates = {
            "mock": (MockRobotController, "Backend/poses/mock_poses.jsonl"),
            "franka": (FrankaController, "Backend/poses/franka_poses.jsonl"),
            "ur": (URController, "Backend/poses/ur_poses.jsonl"),
        }

        for name, (cls, poses_file) in candidates.items():
            try:
                robot = cls(poses_file)
                result = robot.connect()
                if result["success"]:
                    robots[name] = robot
                else:
                    print(f"Warning: {name} failed to connect: {result['message']}")
            except Exception as e:
                print(f"Warning: {name} could not be initialized: {e}")

        return robots

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

            match command:
                case "ping":
                    return self._answer_ping()
                case "get_status":
                    return self._send_status()
                case "execute_sequence":
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
        return self._formatted_response('success', {"Connected Robots": self.robots})

    def _execute_sequence(self, data):
        """Handle execute_sequence command"""

        #Check robot type in data
        robot_type = data.get("robot", "unknown")
        if robot_type not in self.robot_types:
                return self._formatted_response('rejected',{"reason": f"Unsupported robot type: {robot_type}"} )

        # select robot
        robot = self.robots[robot_type]
        responses = []

        # execute commands on robot
        for command in data.get('commands', []):
            response = self._process_command(command, robot)
            responses.append(response)

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

        match action:
            case 'move':
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

            case 'gripper':
                gripper_operation = command['command']
                match gripper_operation:
                    case 'open':
                        response = robot.gripper_open()
                    case 'close':
                        response = robot.gripper_close()
                    case _:
                        return {"error": f"Unknown gripper command: {gripper_operation}"}

                return response

            case 'wait':
                duration_s = command.get('duration_s', 1.0)
                time.sleep(duration_s)
                return {"message": f"Waited for {duration_s} seconds"}

            case 'pose':
                mode = command['command']
                pose_name = command['pose_name']
                overwrite = command.get('overwrite', False)

                match mode:
                    case 'teach':
                        return robot.save_pose(pose_name, overwrite)
                    case 'delete':
                        return robot.delete_pose(pose_name)
                    case _:
                        return {"error": f"Unknown pose management mode: {mode}"}

            case _:
                return {"error": f"Unknown action: {action}"}





