from robot_controllers.mock_robot_controller import MockRobotController

class MessageHandler:
    """Processes commands - no knowledge of communication protocol"""

    def __init__(self):
        """Initialize handler - later will include robot controller, logger"""

        self.allowed_commands = ['ping', 'get_status', 'execute_sequence']
        self.robot_types = ['franka', 'ur', 'mock']  # Supported robot types
        self.robots = self._initialize_robots(config={})  # Placeholder for config


    def _initialize_robots(self, config):
        """Create robot instances based on config"""
        robots = {}

        # For now, hardcoded - later load from config file
        robots["mock"] = MockRobotController()
        robots["mock"].connect()

        # Later add:
        # robots["franka"] = FrankaController(config["franka"]["ip"])
        # robots["ur"] = URController(config["ur"]["ip"])
        # OR
        ''' 
        def _initialize_robots(self, config):
    """Create robot instances based on config"""
    robots = {}

    for robot_type, settings in config.get('robots', {}).items():
        match robot_type:
            case 'mock':
                robots[robot_type] = MockRobotController()
                robots[robot_type].connect(settings)
            case 'franka':
                robots[robot_type] = FrankaController(ip=settings['ip'])
                robots[robot_type].connect()
            case 'ur':
                robots[robot_type] = URController(ip=settings['ip'])
                robots[robot_type].connect()
            case _:
                continue  # Skip unsupported robot types

    return robots

        '''

        return robots

    def _formatted_response(self, command: str, data: dict) -> dict:
        """Format response as JSON with standard structure."""
        return {
            "command": command,
            "data": data
        }

    def process(self, message):
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

        # execute commands on robot


        return self._formatted_response('success', {'message': 'All commands executed'})

    #def _action_handler(self, data):

