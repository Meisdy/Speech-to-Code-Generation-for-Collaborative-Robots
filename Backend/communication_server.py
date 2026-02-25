import zmq
from Backend.message_handler import MessageHandler
import logging
import signal

logger = logging.getLogger("cobot_backend")

class ServerZeroMQ:
    def __init__(self, bind_address):
        """
        bind_address: "tcp://*:5555"
        message_handler: MessageHandler instance to process commands
        """
        self.bind_address = bind_address
        self.handler = MessageHandler()
        self.running = False

        # Initialize ZeroMQ
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(bind_address)
        self.socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 sec timeout for interruptibility

    def start(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self.running = True
        logger.info('Server ready and listening')
        try:
            while self.running:
                try:
                    message = self.socket.recv_json()
                    logger.info('Message received')
                    logger.debug(f'Received message: {message}')
                    response = self.handler.process_message(message=message)
                    self.socket.send_json(response)
                    logger.info('Response sent')
                    logger.debug(f'Sent response: {response}')
                except zmq.Again:
                    continue
                except Exception as e:
                    logger.error('Error in main server loop: %s', e)
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received')
        finally:
            self.close()

    def _handle_signal(self, sig, frame):
        logger.info('Signal %s received, shutting down', sig)
        self.running = False

    def close(self):
        """Clean shutdown"""
        logger.info('Shutting down server')
        self.handler.disconnect_robot()
        self.running = False
        self.socket.close()
        self.context.term()