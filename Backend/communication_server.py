import zmq
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
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

    def start(self):
        """Main server loop with poller for interruptibility."""
        self.running = True
        logger.info('Server ready and listening')

        try:
            while self.running:
                # Poll with timeout to allow KeyboardInterrupt
                socks = dict(self.poller.poll(timeout=1000))  # 1 sec timeout
                if socks.get(self.socket) == zmq.POLLIN:
                    message = self.socket.recv_json()
                    logger.info('Message received')
                    response = self.handler.process_message(message=message)
                    self.socket.send_json(response)
                    logger.info('Response sent')
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received')
        except Exception as e:
            logger.error('Error in server loop: %s', e)
        finally:
            self.close()

    def close(self):
        """Clean shutdown."""
        logger.info('Shutting down server')
        self.running = False
        self.socket.close()
        self.context.term()
