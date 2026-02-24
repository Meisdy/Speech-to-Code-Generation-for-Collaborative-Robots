# config.py
"""
Configuration for Speech-to-Code Framework
All values can be edited directly in this file
"""

import os
FRAMEWORK_MODE = "live"              # Add programming / advanced mode later


# =================================================================================
# ASR (Automatic Speech Recognition) Configuration
# =================================================================================
ASR_MODEL_SIZE = "base"              # Options: tiny, base, small, medium, large
ASR_LANGUAGE = "en"                  # ISO language code, en, de, etc.
ASR_SAMPLE_RATE = 16000              # Hz (Whisper expects 16kHz)
ASR_CONFIDENCE_THRESHOLD = 0.7       # Reject transcripts below this (0.0-1.0)
ASR_FP16 = False                     # Use GPU acceleration (requires CUDA)

# =================================================================================
# Parser Configuration (add as you build parser)
# =================================================================================
LLM_API_BASE = "http://localhost:1234/v1"
LLM_MODEL_NAME = "meta-llama-3.1-8b-instruct"   # Update to your loaded model
LLM_TEMPERATURE = 0.1                           # Low for deterministic output
LLM_MAX_TOKENS = 2048
LLM_TIMEOUT = 60                              # seconds


# =================================================================================
# Robot Backend Configuration
# =================================================================================
BACKEND_IP = "tcp://localhost:5555"
ROBOT_TYPES= ['Franka Emika', 'Universal Robot', 'Mock Adapter']  # Supported robot types
ROBOT_IP = None                             # Robot IP address (None for mock)
ROBOT_TIMEOUT = 5                           # Connection timeout in seconds


# =================================================================================
# Logging Configuration
# =================================================================================
LOGGING_LEVEL = "INFO"               # Options: DEBUG, INFO, WARNING, ERROR (for gui and console)
LOGGING_LEVEL_FILE = "DEBUG"         # Log level for file output (can be more verbose than console/gui)
LOGGING_SAVE_AUDIO = False           # Save audio files for debugging
LOGGING_SAVE_PARSE = False           # Save parser outputs for debugging
DATA_DIR = "data"