from .communication_server import ServerZeroMQ
from .logging_setup import setup_logging

BINDING_ADDRESS = "tcp://*:5555"  # Changed from localhost - binds to all interfaces


def main():
    """Main entry point for robot backend server"""

    # Initialize logger
    logger = setup_logging()
    logger.info(f"Starting backend server on {BINDING_ADDRESS}")

    # Initialize server
    server = ServerZeroMQ(BINDING_ADDRESS)

    # Start server loop
    try:
        server.start()  # Should block here
    except Exception as e:
        logger.exception(f"Server error: {e}")
        server.close()


if __name__ == "__main__":
    main()
