# speech_module.py
import whisper
import pyaudio
import numpy as np
import threading
import config

"""
Notes:
- Consider adding logging statements for debugging and performance monitoring
- Consider adding a method to save audio files for debugging if LOGGING_SAVE_AUDIO is True
- Consider adding a timeout for recording to prevent infinite loops
- Consider adding support for microphone choice (currently uses default input device of computer)
- Consider exploring GPU acceleration with fp16 if performance is an issue
"""


class SpeechRecognizer:
    """
        Speech recognition module using OpenAI's Whisper model.

        Handles audio capture from microphone and transcription to text.
        Designed to be controlled by Pipeline orchestration layer.

        Usage:
            asr = SpeechRecognizer()
            asr.start_listening()
            # ... read_chunk() in loop ...
            audio = asr.stop_listening()
            result = asr.transcribe(audio)
        """
    def __init__(self):
        # Parameters from config
        self.language: str = config.ASR_LANGUAGE
        self.threshold: float = config.ASR_CONFIDENCE_THRESHOLD
        self.sample_rate: int = config.ASR_SAMPLE_RATE
        self.use_fp16: bool = config.ASR_FP16

        # Recording data
        self.stream: pyaudio.Stream | None = None
        self.frames: list[bytes] = []

        # Load Whisper model and PyAudio
        try:
            self.model = whisper.load_model(config.ASR_MODEL_SIZE)
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model '{config.ASR_MODEL_SIZE}': {e}")

        try:
            self.audio_interpreter: pyaudio.PyAudio = pyaudio.PyAudio()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize PyAudio: {e}")

        # Start listening immediately to reduce latency
        self.start_listening()

    # Audio capture methods
    def start_listening(self) -> None:
        """Open stream and prepare for recording."""
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
            raise RuntimeError(f"Failed to open audio stream: {e}")

    def is_listening(self) -> bool:
        """Check if stream is open and ready."""
        return self.stream is not None

    def get_audio(self) -> np.ndarray | None:
        """
        Retrieve recorded audio and reset for next recording.
        Stream remains open for instant next capture.
        """
        if not self.frames:
            return None

        audio = np.frombuffer(b''.join(self.frames), dtype=np.int16)
        self.frames = []  # Clear for next recording

        # Normalize int16 to float32 range [-1.0, 1.0] for Whisper
        return audio.astype(np.float32) / 32768.0

    def close(self) -> None:
        """Clean up audio resources safely."""
        try:
            # Close stream if open
            if self.stream:
                self.stream.close()
                self.stream = None

            # Terminate PyAudio
            if hasattr(self, 'audio_interpreter') and self.audio_interpreter:
                self.audio_interpreter.terminate()
                self.audio_interpreter = None
        except (OSError, AttributeError) as e:
            print(f"Warning: Error closing PyAudio: {e}")


    def read_chunk(self) -> None:
        """Internal: read one chunk (called by pipeline loop)."""
        if self.stream:
            data = self.stream.read(1024, exception_on_overflow=False)
            self.frames.append(data)

    def transcribe(self, audio: np.ndarray | None) -> dict:
        """Convert audio to text using OpenAI's Whisper."""
        if audio is None:
            return {"text": "", "confidence": 0.0}

        try:
            result = self.model.transcribe(audio=audio, language=self.language, fp16=self.use_fp16)
        except Exception as e:
            print(f"Transcription error: {e}")
            return {"text": "", "confidence": 0.0}

        text = result["text"].strip()

        # Calculate confidence: Whisper outputs no_speech_prob per segment
        # Confidence = 1 - average(no_speech_prob) across all segments
        segments = result.get("segments", [])
        if segments:
            avg_no_speech = sum(seg.get("no_speech_prob", 0.0) for seg in segments) / len(segments)
            confidence = 1.0 - avg_no_speech
        else:
            confidence = 0.0

        return {"text": text, "confidence": round(confidence, 2)}


    # Support context manager and cleanup
    def __del__(self):
        """Ensure resources are cleaned up on deletion."""
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
        return False


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