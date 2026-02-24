import zmq
from .message_handler import MessageHandler
import logging

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
        """Main server loop - receives messages and delegates to handler"""
        self.running = True
        logger.info('Server ready and listening')

        while self.running:
            try:
                # Receive message
                message = self.socket.recv_json()
                logger.info('Message received')
                logger.debug('Received message: %s', message)

                # Delegate to handler
                response = self.handler.process_message(message=message)

                # Send response
                self.socket.send_json(response)
                logger.info('Response sent')
                logger.debug('Sent response: %s', response)

            except zmq.Again:
                continue
            except KeyboardInterrupt:
                logger.info('Keyboard interrupt in server loop occured')
                break
            except Exception as e:
                logger.error('Error in main server loop: %s', e)

        self.close()

    def close(self):
        """Clean shutdown"""
        logger.info('Shutting down server')
        self.running = False
        self.socket.close()
        self.context.term()
