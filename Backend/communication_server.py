import zmq
import threading
import logging
from .message_handler import MessageHandler

logger = logging.getLogger("cobot_backend")

class ServerZeroMQ:
    def __init__(self, bind_address):
        self.bind_address = bind_address
        self.handler = MessageHandler()
        self.running = False
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(bind_address)
        self.server_thread = None

    def _server_loop(self):
        """Internal server loop running in a thread."""
        while self.running:
            try:
                message = self.socket.recv_json()
                logger.info('Message received')
                response = self.handler.process_message(message=message)
                self.socket.send_json(response)
                logger.info('Response sent')
            except zmq.Again:
                continue
            except Exception as e:
                logger.error('Error in server loop: %s', e)

    def start(self):
        """Starts the server in a background thread."""
        self.running = True
        logger.info('Server ready and listening')
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()

        # Block the main thread until KeyboardInterrupt
        try:
            while self.running:
                self.server_thread.join(timeout=1)
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received')

        self.close()

    def close(self):
        """Clean shutdown."""
        logger.info('Shutting down server')
        self.running = False
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1)
        self.socket.close()
        self.context.term()
