class MessageHandler:
    """Processes commands - no knowledge of communication protocol"""

    def __init__(self):
        """Initialize handler - later will include robot controller, logger"""
        pass

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

            # Route to appropriate handler method
            if command == "execute_sequence":
                return self._execute_sequence(data)
            elif command == "ping":
                return self._ping(data)
            else:
                return self._unknown_command(command)

        except Exception as e:
            return {
                "command": "error",
                "data": {"error": str(e)}
            }

    def _execute_sequence(self, data):
        """Handle execute_sequence command"""
        # TODO: Call robot controller
        return {
            "command": "success",
            "data": {
                "message": "Sequence executed",
                "received_data": data
            }
        }

    def _ping(self, data):
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
