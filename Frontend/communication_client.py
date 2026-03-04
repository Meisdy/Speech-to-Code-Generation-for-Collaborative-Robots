import zmq

MAX_ATTEMPTS = 2

class ClientZeroMQ:
    def __init__(self, connection_string, timeout_ms=15000):
        """
        connection_string: "tcp://192.168.1.10:5555" or "tcp://localhost:5556"
        timeout_ms: Response timeout in milliseconds
        """
        self.connection_str : str = connection_string
        self.timeout_ms : int = timeout_ms
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        self.socket.connect(connection_string)

    def _reconnect(self):
        self.socket.close()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.connect(self.connection_str)

    def send_command(self, command_str, data_dict):
        message = {"command": command_str, "data": data_dict}
        for attempt in range(MAX_ATTEMPTS):
            try:
                self.socket.send_json(message)
                response = self.socket.recv_json()
                return True, response
            except zmq.Again:
                self._reconnect()
            except Exception as e:
                return False, {"command": "error", "data": {"error": str(e)}}
        return False, {"command": "timeout",
                       "data": {"error": f"Backend unreachable after {MAX_ATTEMPTS} attempts"}}

    def close(self) -> None:
        self.socket.setsockopt(zmq.LINGER, 0) # needed so we can close upon timeout
        self.socket.close()
        self.context.term()


def main():
    sender = ClientZeroMQ("tcp://localhost:5555")

    data = {
        "mode": "live",
        "robot": "ur",
        "commands": [
            {
                "action": "move",
                "motion_type": "moveJ",
                "target": {
                    "type": "named_pose",
                    "name": "home_position"
                }
            },
            {
                "action": "gripper",
                "command": "open"
            },
            {
                "action": "wait",
                "duration_s": 0.5
            }
        ],
        "message": ""
    }

    # Example command
    #success, response = sender.send_command("ping", {"message": "Hello from client!"})
    #success, response = sender.send_command("get_status", {"message": "Hello from client!"})
    #success, response = sender.send_command("Hallo", {"message": "Hello from client!"})
    success, response = sender.send_command("execute_sequence", data)

    if success:
        print("Received response:", response)
    else:
        print("Failed to send command:", response)

    sender.close()


if __name__ == "__main__":
    main()