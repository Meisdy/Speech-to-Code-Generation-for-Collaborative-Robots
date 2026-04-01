"""
config_frontend.py — Configuration for Speech-to-Code Framework.
All values can be edited directly in this file.
"""
import os

# ── ASR ───────────────────────────────────────────────────────────────────────
ASR_MODEL_SIZE           = "small"    # tiny | base | small | medium | large
ASR_LANGUAGE             = "en"      # ISO language code
ASR_SAMPLE_RATE          = 16000     # Hz — Whisper expects 16kHz
ASR_CONFIDENCE_THRESHOLD = 0.7      # Warn on transcripts below this (0.0–1.0)
ASR_FP16                 = False     # Requires CUDA (not yet implemented)

# ── LLM Parser ────────────────────────────────────────────────────────────────
LLM_API_BASE    = "http://localhost:1234/v1"
LLM_MODEL_NAME  = "meta-llama-3.1-8b-instruct"
LLM_TEMPERATURE = 0.1               # Low = more deterministic output
LLM_MAX_TOKENS  = 2048
LLM_TIMEOUT     = 60                # Long — LLM may need to load on first call

# ── Backend ───────────────────────────────────────────────────────────────────
BACKEND_IPS = {
    "franka": "tcp://192.168.2.20:5555",    # Backend runs on Linux PC for Franka
    "ur":     "tcp://localhost:5555",       # Backend runs on Operator machine for UR
    "mock":   "tcp://localhost:5555",       # Backend runs on Operator machinie for Mock
}

ROBOT_TYPE_KEYS = {                         # Are used in GUI and for backend robot type matching
    "Franka Emika":    "franka",
    "Universal Robot": "ur",
    "Mock Adapter":    "mock",
}

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING_LEVEL      = "INFO"     # Console and GUI level: DEBUG | INFO | WARNING | ERROR
LOGGING_LEVEL_FILE = "DEBUG"    # File level — can be more verbose than console
LOGGING_SAVE_AUDIO = False      # Save .wav files for ASR debugging
LOGGING_SAVE_PARSE = False      # Save parsed JSON for parser debugging
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")