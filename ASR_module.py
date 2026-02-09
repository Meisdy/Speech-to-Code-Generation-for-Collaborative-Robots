# speech_module.py
import whisper
import pyaudio
import numpy as np
import threading
import config


class SpeechRecognizer:
    def __init__(self):
        # Add a logging statement to confirm initialization here later
        self.model = whisper.load_model(config.ASR_MODEL_SIZE)
        self.language = config.ASR_LANGUAGE
        self.threshold = config.ASR_CONFIDENCE_THRESHOLD
        self.sample_rate = config.ASR_SAMPLE_RATE
        self.audio_interpreter = pyaudio.PyAudio()
        self.use_fp16 = config.ASR_FP16 # check out GPU support later, if needed

    def listen(self):
        """
        Record audio from main device microphone using push-to-talk (Enter key).

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
        stop_event.set()
        thread.join()

        stream.close()

        # Convert raw bytes to normalized float32 array
        if frames:
            recorded_audio = np.frombuffer(b''.join(frames), dtype=np.int16)
            return recorded_audio.astype(np.float32) / 32768.0
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

    # Updated test code
if __name__ == "__main__":
    asr = SpeechRecognizer()

    audio = asr.listen()
    result = asr.transcribe(audio)
    print(f"\nFinal text: {result['text']}")
    print(f"Confidence: {result['confidence']}")
