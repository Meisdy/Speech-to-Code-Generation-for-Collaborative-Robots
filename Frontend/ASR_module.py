"""
Speech recognition module using OpenAI Whisper.
Handles microphone audio capture and transcription for the speech-to-code pipeline.
"""
import logging
import os
import threading
import wave
from datetime import datetime

import numpy as np
import pyaudio
import whisper

import Frontend.config_frontend as config_frontend

logger = logging.getLogger("cobot")


class SpeechRecognizer:
    """Handles microphone capture and Whisper transcription for the pipeline."""

    def __init__(self):
        self.model_size: str = config_frontend.ASR_MODEL_SIZE
        self.language: str = config_frontend.ASR_LANGUAGE
        self.threshold: float = config_frontend.ASR_CONFIDENCE_THRESHOLD
        self.sample_rate: int = config_frontend.ASR_SAMPLE_RATE
        self.use_fp16: bool = config_frontend.ASR_FP16
        self.log_audio: bool = config_frontend.LOGGING_SAVE_AUDIO
        self.log_path: str = config_frontend.DATA_DIR

        self.stream: pyaudio.Stream | None = None
        self.frames: list[bytes] = []

        # Errors here propagate to Controller.__init__ and are caught in main.py
        self.model = whisper.load_model(self.model_size)
        self.audio_interpreter: pyaudio.PyAudio = pyaudio.PyAudio()
        self.start_listening()

    def start_listening(self) -> None:
        """Open audio stream and prepare for recording."""
        self.frames = []
        self.stream = self.audio_interpreter.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=1024
        )

    def is_listening(self) -> bool:
        """Return True if the audio stream is open."""
        return self.stream is not None

    def read_chunk(self) -> None:
        """Read one audio chunk from stream (called by pipeline loop)."""
        if self.stream:
            data = self.stream.read(1024, exception_on_overflow=False)
            self.frames.append(data)

    def get_audio(self) -> np.ndarray | None:
        """Return recorded audio as normalized float32 and reset the buffer."""
        if not self.frames:
            return None

        audio = np.frombuffer(b''.join(self.frames), dtype=np.int16)
        self.frames = []  # Clear for next recording

        if self.log_audio:
            self._save_audio(audio)

        # Whisper expects float32 in [-1.0, 1.0]
        return audio.astype(np.float32) / 32768.0

    def transcribe(self, audio: np.ndarray | None) -> dict:
        """Convert audio array to text using Whisper. Returns text and confidence."""
        if audio is None:
            return {"text": "", "confidence": 0.0}

        try:
            result = self.model.transcribe(audio=audio, language=self.language, fp16=self.use_fp16)
        except Exception as e:  # Whisper does not document specific exceptions
            logger.exception("Transcription failed: %s", e)
            return {"text": "", "confidence": 0.0}

        text = result["text"].strip()

        # Confidence = 1 - average no_speech_prob across segments
        segments = result.get("segments", [])
        if segments:
            avg_no_speech = sum(seg.get("no_speech_prob", 0.0) for seg in segments) / len(segments)
            confidence = 1.0 - avg_no_speech
        else:
            # No segment metadata doesn't mean silence — don't penalise valid transcriptions
            confidence = 1.0 if text else 0.0

        logger.info("ASR: transcribed text '%s', confidence = %.2f", text, confidence)
        return {"text": text, "confidence": round(confidence, 2)}

    def close(self) -> None:
        """Clean up audio resources safely."""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            if self.audio_interpreter:
                self.audio_interpreter.terminate()
                self.audio_interpreter = None
        except (OSError, AttributeError) as e:
            logger.error("Error closing PyAudio: %s", e)

    def _save_audio(self, audio: np.ndarray) -> None:
        """Save recorded audio to the data folder for debugging."""
        try:
            os.makedirs(self.log_path, exist_ok=True)
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
            filepath = os.path.join(self.log_path, f"{timestamp}_audio.wav")

            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio.tobytes())

            logger.info("Saved audio to %s", filepath)

        except OSError as e:
            logger.error("Failed to save debug audio: %s", e)


def main() -> None:
    """Test SpeechRecognizer standalone."""
    asr = SpeechRecognizer()

    print("Press ENTER to start recording...")
    input()

    recording = threading.Event()
    recording.set()
    print("🔴 Recording... (press ENTER to stop)")

    def record_loop():
        while recording.is_set():
            asr.read_chunk()

    thread = threading.Thread(target=record_loop, daemon=True)
    thread.start()

    input()
    recording.clear()
    thread.join()

    audio = asr.get_audio()
    result = asr.transcribe(audio)
    print(f"\nFinal text: {result['text']}")
    print(f"Confidence: {result['confidence']}")

    asr.close()


if __name__ == "__main__":
    main()
