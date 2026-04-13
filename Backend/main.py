"""Main entry point for backend. Is written to be downwards compatible with python 3.8, to allow for ROS1 franka stack to work"""

from Backend.communication_server import ServerZeroMQ
from Backend.logging_setup import setup_logging
from Backend.config_backend import BINDING_ADDRESS


def main() -> None:
    """Entry point for the robot backend server."""
    logger = setup_logging()
    logger.info("Starting backend server on %s", BINDING_ADDRESS)

    server = ServerZeroMQ(BINDING_ADDRESS)

    try:
        server.start()
    except Exception as e:
        logger.exception("Unhandled server error: %s", e)


if __name__ == "__main__":
    main()
