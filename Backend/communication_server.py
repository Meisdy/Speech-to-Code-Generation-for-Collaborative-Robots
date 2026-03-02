import logging
import signal

import zmq

from Backend.message_handler import MessageHandler
from Backend.config_backend import ZMQ_TIMEOUT_MS

logger = logging.getLogger("cobot_backend")


class ServerZeroMQ:
    """ZeroMQ REP server that receives commands and dispatches them via MessageHandler."""

    def __init__(self, bind_address: str) -> None:
        self.bind_address = bind_address
        self.handler = MessageHandler()
        self.running : bool = False
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)

    def start(self) -> None:
        """Bind socket, register signals, and enter the receive-respond loop."""
        self.socket.bind(self.bind_address)
        self.socket.setsockopt(zmq.RCVTIMEO, ZMQ_TIMEOUT_MS)  # allows clean interrupt checks
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self.running = True
        logger.info("Server ready and listening on %s", self.bind_address)

        try:
            while self.running:
                try:
                    message = self.socket.recv_json()
                    logger.debug(f"Received message: {message}")
                    response = self.handler.process_message(message=message)
                    self.socket.send_json(response)
                    logger.debug(f"Sent response: {response}")
                except zmq.Again:
                    continue
                except zmq.ZMQError as e:
                    logger.error(f"ZMQ error in server loop: {e}")
        finally:
            self.close()

    def close(self) -> None:
        """Disconnect robot and tear down ZMQ resources."""
        logger.info("Shutting down server")
        self.handler.disconnect_robot()
        self.socket.close()
        self.context.term()

    def _handle_signal(self, sig, frame: object):
        logger.info('Signal %s received, shutting down', sig)
        self.running = False
