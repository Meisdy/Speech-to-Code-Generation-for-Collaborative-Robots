import zmq


class ClientZeroMQ:
    def __init__(self, connection_string, timeout_ms=5000):
        """
        connection_string: "tcp://192.168.1.10:5555" or "tcp://localhost:5556"
        timeout_ms: Response timeout in milliseconds
        """
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        self.socket.connect(connection_string)

    def send_command(self, command_str, data_dict):
        """
        Send command and wait for response.
        Returns: (success: bool, response_dict: dict)
        """
        message = {
            "command": command_str,
            "data": data_dict
        }

        try:
            self.socket.send_json(message)
            response = self.socket.recv_json()
            return True, response
        except zmq.Again:
            # Timeout - backend not responding
            return False, {"command": "timeout", "data": {"error": "Backend timeout"}}
        except Exception as e:
            return False, {"command": "error", "data": {"error": str(e)}}

    def close(self):
        self.socket.close()
        self.context.term()


def main():
    sender = ClientZeroMQ("tcp://localhost:5555")

    # Example command
    success, response = sender.send_command("move_forward", {"distance": 1.0})
    if success:
        print("Received response:", response)
    else:
        print("Failed to send command:", response)

    sender.close()


if __name__ == "__main__":
    main()