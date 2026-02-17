from communication_server import ServerZeroMQ

BINDING_ADDRESS = "tcp://*:5555"  # Changed from localhost - binds to all interfaces


def main():
    """Main entry point for robot backend server"""

    # Initialize server
    server = ServerZeroMQ(BINDING_ADDRESS)
    print(f"Starting backend server on {BINDING_ADDRESS}")

    # Start server loop
    try:
        server.start()  # Should block here
    except Exception as e:
        print(f"Server error: {e}")
        server.close()


if __name__ == "__main__":
    main()
