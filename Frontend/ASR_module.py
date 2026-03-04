# speech_module.py
"""
Speech recognition module using OpenAI Whisper.
Handles microphone audio capture and transcription for the speech-to-code pipeline.
"""
import whisper
import pyaudio
import numpy as np
import threading
import Frontend.config_frontend as config_frontend
import logging
import wave
import os
from datetime import datetime

logger = logging.getLogger("cobot")


class SpeechRecognizer:
    """
    Speech recognition module using OpenAI's Whisper model.

    Handles audio capture from microphone and transcription to text.
    Designed to be controlled by Pipeline orchestration layer.
    """

    def __init__(self):
        # Parameters from config
        self.model_size: str = config_frontend.ASR_MODEL_SIZE
        self.language: str = config_frontend.ASR_LANGUAGE
        self.threshold: float = config_frontend.ASR_CONFIDENCE_THRESHOLD
        self.sample_rate: int = config_frontend.ASR_SAMPLE_RATE
        self.use_fp16: bool = config_frontend.ASR_FP16
        self.log_audio: bool = config_frontend.LOGGING_SAVE_AUDIO
        self.log_path: str = config_frontend.DATA_DIR

        # Recording data
        self.stream: pyaudio.Stream | None = None
        self.frames: list[bytes] = []

        # Load Models and start listening (Errors in this will be caught in the init
        self.model = whisper.load_model(self.model_size)
        self.audio_interpreter: pyaudio.PyAudio = pyaudio.PyAudio()
        self.start_listening()

    def start_listening(self) -> None:
        """
        Open audio stream and prepare for recording.

        Raises:
            RuntimeError: If audio stream cannot be opened.
        """
        self.frames = []
        try:
            self.stream = self.audio_interpreter.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=1024
            )
        except OSError as e:
            logger.exception(f"Failed to open audio stream: {e}")

    def is_listening(self) -> bool:
        """
        Check if audio stream is open and ready.

        Returns:
            bool: True if stream is active, False otherwise.
        """
        return self.stream is not None

    def get_audio(self) -> np.ndarray | None:
        """
        Retrieve recorded audio and reset for next recording.

        Stream remains open for instant next capture.

        Returns:
            np.ndarray: Normalized float32 audio in range [-1.0, 1.0], or None if no frames recorded.
        """
        if not self.frames:
            return None

        audio = np.frombuffer(b''.join(self.frames), dtype=np.int16)
        self.frames = []  # Clear for next recording

        # Optionally save audio for debugging
        if self.log_audio:
            self._save_audio(audio)

        # Normalize int16 to float32 range [-1.0, 1.0] for Whisper
        return audio.astype(np.float32) / 32768.0

    def transcribe(self, audio: np.ndarray | None) -> dict:
        """
        Convert audio to text using OpenAI's Whisper.

        Args:
            audio (np.ndarray): Normalized float32 audio array from get_audio().

        Returns:
            dict: Dictionary with 'text' (str) and 'confidence' (float) keys.
        """
        if audio is None:
            return {"text": "", "confidence": 0.0}

        try:
            result = self.model.transcribe(audio=audio, language=self.language, fp16=self.use_fp16)
        except Exception as e:
            logger.exception(f"Transcription failed: {e}")
            return {"text": "", "confidence": 0.0}

        text = result["text"].strip()

        # Calculate confidence: Whisper outputs no_speech_prob per segment
        # Confidence = 1 - average(no_speech_prob) across all segments
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
            if hasattr(self, 'audio_interpreter') and self.audio_interpreter:
                self.audio_interpreter.terminate()
                self.audio_interpreter = None
        except (OSError, AttributeError) as e:
            logger.error(f"Error closing PyAudio: {e}")

    def read_chunk(self) -> None:
        """Read one audio chunk from stream (called by pipeline loop)."""
        if self.stream:
            data = self.stream.read(1024, exception_on_overflow=False)
            self.frames.append(data)

    def _save_audio(self, audio: np.ndarray) -> None:
        """Save recorded audio to logs folder for debugging."""
        try:
            # Generate timestamp-based filename
            os.makedirs(self.log_path, exist_ok=True)  # ensure dir exists
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
            filepath = os.path.join(self.log_path, f"{timestamp}_audio.wav")

            # Write WAV file
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(1)  # Mono
                wf.setsampwidth(2)  # 2 bytes = 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio.tobytes())

            logger.info(f"Saved audio to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save debug audio: {e}")


# Example usage (for testing purposes)
def main():
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

    input()  # Wait for user to stop
    recording.clear()
    thread.join()

    # Get audio (stream stays open)
    audio = asr.get_audio()
    result = asr.transcribe(audio)

    print(f"\nFinal text: {result['text']}")
    print(f"Confidence: {result['confidence']}")

    asr.close()  # Only close on exit


if __name__ == "__main__":
    main()
