BINDING_ADDRESS     = "tcp://*:5555"                                # Binding address for backend ZeroMQ Server
ZMQ_TIMEOUT_MS      = 1000                                          # Timeout for ZeroMQ that allows for interrupt checking
AVAILABLE_ROBOTS    = ["mock", "franka", "ur"]                      # ur, franka, mock : Add new adapter here
ALLOWED_COMMANDS    = ["ping", "execute_sequence",                  # allowed main level commands for backend to accept
                       "save_script", "run_script", "stop_script",
                       "get_script_status", "delete_script"]
LOGGING_LEVEL       = "INFO"                                        # Log level for console, Options: DEBUG, INFO, WARNING, ERROR (for console)
LOGGING_LEVEL_FILE  = "DEBUG"                                       # Log level for file output in Backend/log/
PC_IP               = "192.168.1.101"                               # your Backend PC IP as seen by the UR Robot. Needed for callback for finished pos
