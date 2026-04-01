import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # package root resolution for python devices without IDE auto add

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
