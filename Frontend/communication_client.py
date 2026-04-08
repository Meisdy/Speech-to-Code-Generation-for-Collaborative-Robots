"""ZeroMQ client for sending commands to the robot backend."""

import logging

import zmq

from Frontend.config_frontend import MAX_ATTEMPTS

logger = logging.getLogger("cobot")


class ClientZeroMQ:
    """REQ/REP ZeroMQ client with timeout and reconnect on failure."""

    def __init__(self, connection_string: str, timeout_ms: int = 30000) -> None:
        """
        Args:
            connection_string: ZeroMQ endpoint, e.g. "tcp://192.168.2.20:5555"
            timeout_ms: Receive timeout in milliseconds
        """
        self.connection_str = connection_string
        self.timeout_ms = timeout_ms
        self.context = zmq.Context()
        self.socket = self._make_socket()

    def send_command(self, command_str: str, data_dict: dict) -> tuple[bool, dict]:
        """Send a command to the backend and return (success, response)."""
        message = {"command": command_str, "data": data_dict}
        for _ in range(MAX_ATTEMPTS):
            try:
                self.socket.send_json(message)
                response = self.socket.recv_json()
                return True, response
            except zmq.Again:
                # Timeout — reset socket state before retrying
                self._reconnect()
            except Exception as e:
                logger.error("Client: Unexpected ZeroMQ error: %s", e)
                return False, {"command": "error", "data": {"error": str(e)}}
        return False, {"command": "timeout",
                       "data": {"error": f"Backend unreachable after {MAX_ATTEMPTS} attempts"}}

    def close(self) -> None:
        """Close socket and terminate ZeroMQ context."""
        self.socket.close()
        self.context.term()

    def _make_socket(self) -> zmq.Socket:
        """Create and configure a new REQ socket."""
        socket = self.context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)  # Discard pending messages on close, prevents hangs
        socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        socket.connect(self.connection_str)
        return socket

    def _reconnect(self) -> None:
        """Replace the current socket with a fresh one."""
        self.socket.close()
        self.socket = self._make_socket()


def main() -> None:
    """Test client with a sample execute_sequence command."""
    sender = ClientZeroMQ("tcp://localhost:5555")

    data = {
        "robot": "mock",
        "commands": [
            {"action": "move", "motion_type": "moveJ", "target": {"type": "named_pose", "name": "home"}},
            {"action": "gripper", "command": "open"},
            {"action": "wait", "duration_s": 0.5}
        ],
        "message": ""
    }

    success, response = sender.send_command("execute_sequence", data)
    print("Response:" if success else "Failed:", response)
    sender.close()


if __name__ == "__main__":
    main()