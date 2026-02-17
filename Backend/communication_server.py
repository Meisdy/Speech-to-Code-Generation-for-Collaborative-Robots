import zmq
from message_handler import MessageHandler

class ServerZeroMQ:
    def __init__(self, bind_address):
        """
        bind_address: "tcp://*:5555"
        message_handler: MessageHandler instance to process commands
        """
        self.bind_address = bind_address
        self.handler = MessageHandler
        self.running = False

        # Initialize ZeroMQ
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(bind_address)
        self.socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 sec timeout for interruptibility

    def start(self):
        """Main server loop - receives messages and delegates to handler"""
        self.running = True
        print(f"Server listening on {self.bind_address}")
        print("Ready to receive commands...")

        while self.running:
            try:
                # Receive message
                message = self.socket.recv_json()
                print(f"Received: {message.get('command', 'unknown')}")

                # Delegate to handler
                response = self.handler.process(message)

                # Send response
                self.socket.send_json(response)
                print(f"Sent: {response.get('command', 'unknown')}")

            except zmq.Again:
                # Timeout - loop continues to check self.running
                continue
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt in server loop")
                break

    def close(self):
        """Clean shutdown"""
        print("Closing server...")
        self.running = False
        self.socket.close()
        self.context.term()
