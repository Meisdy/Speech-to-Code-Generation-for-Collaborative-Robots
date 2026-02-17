class MessageHandler:
    """Processes commands - no knowledge of communication protocol"""

    def __init__(self):
        """Initialize handler - later will include robot controller, logger"""

        self.allowed_commands = ['ping', 'get_status', 'execute_sequence']
        self.robot_types = ['franka', 'ur', 'mock']  # Supported robot types
        self.busy = False  # Flag to indicate if robot is currently executing a command

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
                    if self.busy:
                        return {
                            "command": "rejected",
                            "data": {"reason": "Robot is currently busy executing another command"}
                        }
                    self.busy = True  # Set busy flag before execution
                    try:
                        response = self._execute_sequence(data)
                    finally:
                        self.busy = False  # Reset busy flag after execution
                    return response



        except Exception as e:
            return {
                "command": "error",
                "data": {"error": str(e)}
            }


    def _answer_ping(self) -> dict:
        """Handle ping command"""
        return {
            "command": "success",
            "data": {"message": "Backend alive"}
        }

    def _unknown_command(self, command):
        """Handle unknown commands"""
        return {
            "command": "rejected",
            "data": {"reason": f"Unknown command: {command}"}
        }

    def _send_status(self):
        """Handle get_status command"""
        return {
            "command": "success",
            "data": {"busy": self.busy}
        }

    def _execute_sequence(self, data):
        """Handle execute_sequence command"""
        # TODO: Call robot controller

        #Check robot type in data
        robot_type = data.get("robot", "unknown")
        print('Executing sequence for robot type:', robot_type)
        if robot_type not in self.robot_types:
                return {"command": "rejected", "data": {"reason": f"Unsupported robot type: {robot_type}"}}

        #

        return {
            "command": "success",
            "data": {
                "message": "Sequence executed",
                "received_data": data
            }
        }