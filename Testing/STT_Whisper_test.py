"""
Whisper STT Module - File or Live Mode (GPU Auto + Superfast Option)
MODE = 'FILE' or 'LIVE'
Auto-detects GPU (CUDA) for 3-10x speed boost if available.
Superfast: Swap to faster-whisper (install separately).

Requires: pip install openai-whisper soundfile pyaudio torch torchvision torchaudio
For GPU: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121  (CUDA 12.1)
FFmpeg for FILE is needed on the system aswell.
"""

import whisper
import torch  # For GPU check
import os
import json
import time
import tempfile
import wave
from pathlib import Path
import pyaudio

# Config
MODEL_SIZE = "base"  # tiny/small/medium/large-v3
MODE = 'FILE'  # 'FILE' or 'LIVE'
TEST_AUDIO_FILE = "testrecording.mp3"
RECORD_DURATION = 15
USE_FASTER_WHISPER = False  # Set True after pip install faster-whisper (even faster on GPU)


def get_device():
    """Auto GPU if available, else CPU."""
    if torch.cuda.is_available():
        print(f"✅ GPU detected: {torch.cuda.get_device_name(0)}")
        return "cuda"
    print("⚠️  No CUDA GPU - using CPU")
    return "cpu"


def transcribe_file(audio_path, device):
    """Transcribe from file/mic path with device."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Transcribing {audio_path} with {MODEL_SIZE} on {device}...")

    if USE_FASTER_WHISPER:
        # Superfast alt (CTranslate2 backend, 2-4x original)
        from faster_whisper import WhisperModel
        model = WhisperModel(MODEL_SIZE, device="cuda" if device == "cuda" else "cpu", compute_type="float16")
        segments, info = model.transcribe(audio_path, language="en", beam_size=5)
        text = " ".join(seg.text for seg in segments)
        return {"text": text.strip(), "confidence": info.language_confidence or 0.0, "time_taken": 0.0}  # Simplified

    # Original Whisper
    model = whisper.load_model(MODEL_SIZE, device="cuda")

    start_time = time.time()
    result = model.transcribe(audio_path, language="en", fp16=(device == "cuda"))
    elapsed = time.time() - start_time

    segments = result.get("segments", [])
    avg_conf = 1.0 - (sum(seg.get("no_speech_prob", 0.0) for seg in segments) / max(len(segments), 1))

    return {
        "text": result["text"].strip(),
        "confidence": avg_conf,
        "time_taken": elapsed,
        "segments": [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in segments]
    }


def record_live(duration=RECORD_DURATION):
    """Record mic to temp WAV."""
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    print(f"Recording {duration}s... Speak!")
    frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * duration))]

    stream.stop_stream()
    stream.close()
    p.terminate()

    tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    with wave.open(tmp_path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    return tmp_path


if __name__ == "__main__":
    device = get_device()

    try:
        if MODE.upper() == 'LIVE':
            audio_path = record_live(RECORD_DURATION)
        elif MODE.upper() == 'FILE':
            audio_path = TEST_AUDIO_FILE
        else:
            raise ValueError("MODE: 'FILE' or 'LIVE'")

        result = transcribe_file(audio_path, device)

        print("\n" + "=" * 50)
        print("TRANSCRIPT:", result["text"])
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"Time: {result['time_taken']:.2f}s")

        log_file = f"stt_log_{MODEL_SIZE}_{MODE.upper()}_{device}_{Path(audio_path).stem}.json"
        log_data = {**result, "mode": MODE.upper(), "device": device, "audio_file": audio_path}
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)
        print(f"\nLogged: {log_file}")

        if MODE.upper() == 'LIVE' and os.path.exists(audio_path):
            os.unlink(audio_path)

    except Exception as e:
        print(f"Error: {e}")
        print("GPU: pip install torch... --index-url https://download.pytorch.org/whl/cu121")
        print("Faster: pip install faster-whisper ctranslate2")
