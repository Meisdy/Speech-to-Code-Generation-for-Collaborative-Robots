# speech_module.py
import whisper
import pyaudio
import numpy as np
import threading
import config

"""
To do:
- Add logging statements for debugging and performance monitoring
- Implement error handling for audio capture and transcription?
- Consider adding a timeout for recording to prevent infinite loops
- Explore GPU acceleration with fp16 if performance is an issue
- Add real push-to-talk support with a physical button or keyboard listener instead of blocking input()
- Consider adding a method to save audio files for debugging if LOGGING_SAVE_AUDIO is True
- Add support for different microphones or audio interfaces if needed
"""


class SpeechRecognizer:
    def __init__(self):
        self.model = whisper.load_model(config.ASR_MODEL_SIZE)
        self.language = config.ASR_LANGUAGE
        self.threshold = config.ASR_CONFIDENCE_THRESHOLD
        self.sample_rate = config.ASR_SAMPLE_RATE
        self.audio_interpreter = pyaudio.PyAudio()
        self.use_fp16 = config.ASR_FP16

        # Recording state
        self.stream = None
        self.frames = []
        self.stop_event = None
        self.record_thread = None

    def start_listening(self):
        """Start recording audio in background thread."""
        self.frames = []
        self.stop_event = threading.Event()

        self.stream = self.audio_interpreter.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=1024
        )

        def record():
            while not self.stop_event.is_set():
                data = self.stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)

        self.record_thread = threading.Thread(target=record)
        self.record_thread.start()

    def stop_listening(self):
        """Stop recording and return audio data."""
        if self.stop_event:
            self.stop_event.set()
        if self.record_thread:
            self.record_thread.join()
        if self.stream:
            self.stream.close()

        # Convert to normalized float32
        if self.frames:
            audio = np.frombuffer(b''.join(self.frames), dtype=np.int16)
            return audio.astype(np.float32) / 32768.0
        return None

    def transcribe(self, audio):
        """Convert audio to text using Whisper"""
        if audio is None:
            return {"text": "", "confidence": 0.0}

        result = self.model.transcribe(audio=audio, language=self.language, fp16=self.use_fp16) # Whisper on G16 CPU doesn't support fp16

        text = result["text"].strip()

        # Calculate confidence from no_speech_prob
        segments = result.get("segments", [])
        if segments:
            # Average no_speech_prob across segments, then invert
            avg_no_speech = sum(seg.get("no_speech_prob", 0.0) for seg in segments) / len(segments)
            confidence = 1.0 - avg_no_speech
        else:
            confidence = 0.0  # No segments = no confidence

        return {
            "text": text,
            "confidence": round(confidence, 2)
        }

    def _listen(self):
        """
        Record audio from main device microphone using "push-to-talk" (Enter key).
        Currently, it is not real push to talk, but close enough.

        Flow:
            1. User presses Enter to start recording
            2. Audio captured in background thread
            3. User presses Enter again to stop
            4. Audio converted to normalized float32 array

        Returns:
            np.ndarray: Normalized audio samples [-1.0, 1.0] at 16kHz, or None if no audio captured
        """
        input("\nPress ENTER to start recording...")
        print("🔴 Recording... (press ENTER again to stop)")

        # Start recording in background
        stream = self.audio_interpreter.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=1024
        )

        # Store audio data in memory
        frames = []

        # Record until Enter pressed (non-blocking read)
        stop_event = threading.Event()

        def record():
            """Background thread: continuously read audio chunks"""
            while not stop_event.is_set():
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

        thread = threading.Thread(target=record)
        thread.start()

        input()  # Wait for Enter to stop recording
        stop_event.set() # Signal recording thread to stop
        thread.join() # Wait for thread to finish
        stream.close() # Clean up audio stream

        # Convert raw bytes to normalized float32 array
        if frames:
            recorded_audio = np.frombuffer(b''.join(frames), dtype=np.int16)
            return recorded_audio.astype(np.float32) / 32768.0
        return None


    # Cleanup methods to ensure we don't leave audio resources hanging around. Autocalled or manually called when needed.
    def close(self) -> None:
        """Clean up audio resources safely."""
        try:
            if hasattr(self, 'audio_interpreter') and self.audio_interpreter:
                self.audio_interpreter.terminate()
                self.audio_interpreter = None
        except Exception as e:
            print(f"Warning: Error closing PyAudio: {e}")

    def __del__(self):
        """Ensure resources are cleaned up on deletion."""
        try:
            self.close()
        except Exception:
            pass  # Silently ignore errors in destructor

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
        return False


# Testing method to run ASR module independently
if __name__ == "__main__":
    asr = SpeechRecognizer()

    audio = asr._listen()
    result = asr.transcribe(audio)
    print(f"\nFinal text: {result['text']}")
    print(f"Confidence: {result['confidence']}")
