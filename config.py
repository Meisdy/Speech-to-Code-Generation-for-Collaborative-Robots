# config.py
"""
Configuration for Speech-to-Code Framework
All values can be edited directly in this file
"""

# =================================================================================
# ASR (Automatic Speech Recognition) Configuration
# =================================================================================
ASR_MODEL_SIZE = "base"              # Options: tiny, base, small, medium, large
ASR_LANGUAGE = "en"                  # ISO language code, en, de, etc.
ASR_SAMPLE_RATE = 16000              # Hz (Whisper expects 16kHz)
ASR_CONFIDENCE_THRESHOLD = 0.7       # Reject transcripts below this (0.0-1.0)
ASR_FP16 = False                     # Use GPU acceleration (requires CUDA)

# =================================================================================
# Input Configuration
# =================================================================================
INPUT_METHOD = "keyboard"            # Options: keyboard, button
PTT_TRIGGER = "enter"                # Push-to-talk trigger

# =================================================================================
# Robot Backend Configuration
# =================================================================================
ROBOT_TYPE = "mock"                  # Options: mock, franka, ur
ROBOT_IP = None                      # Robot IP address (None for mock)
ROBOT_TIMEOUT = 5                    # Connection timeout in seconds

# =================================================================================
# Parser Configuration (add as you build parser)
# =================================================================================
PARSER_MAX_COMMAND_LENGTH = 200      # Maximum characters per command

# =================================================================================
# Logging Configuration
# =================================================================================
LOGGING_ENABLED = True               # Enable/disable logging
LOGGING_DIR = "./logs"               # Log output directory
LOGGING_LEVEL = "INFO"               # Options: DEBUG, INFO, WARNING, ERROR
LOGGING_SAVE_AUDIO = False           # Save audio files for debugging
