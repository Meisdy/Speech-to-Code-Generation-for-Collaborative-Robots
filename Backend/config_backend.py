BINDING_ADDRESS     = "tcp://*:5555"                                # Binding address for backend ZeroMQ Server
ZMQ_TIMEOUT_MS      = 1000                                          # Timeout for ZeroMQ
AVAILABLE_ROBOTS    = ["mock", "franka", "ur"]                      # ur, franka, mock : Add new adapter here
ALLOWED_COMMANDS    = ["ping", "get_status", "execute_sequence"]    # allowed main level commands for backend to accept
LOGGING_LEVEL       = "INFO"                                        # Log level for console, Options: DEBUG, INFO, WARNING, ERROR (for console)
LOGGING_LEVEL_FILE  = "DEBUG"                                       # Log level for file output in Backend/log/