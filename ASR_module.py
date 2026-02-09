# speech_module.py - No external keyboard library needed
import whisper
import pyaudio
import numpy as np
import json
import threading

with open('config.json', 'r') as f:
    config = json.load(f)


class SpeechRecognizer:
    def __init__(self):
        print("Loading Whisper model...")
        self.model = whisper.load_model(config['asr']['model_size'])
        self.audio = pyaudio.PyAudio()
        print("Ready!")

    def listen(self):
        """Record audio with simple start/stop prompts"""
        input("\nPress ENTER to start recording...")
        print("🔴 Recording... (press ENTER again to stop)")

        # Start recording in background
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=config['asr']['sample_rate'],
            input=True,
            frames_per_buffer=1024
        )

        # Store audio data in memory
        frames = []

        # Record until Enter pressed (non-blocking read)
        stop_event = threading.Event()

        def record():
            while not stop_event.is_set():
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

        thread = threading.Thread(target=record)
        thread.start()

        input()  # Wait for Enter
        stop_event.set()
        thread.join()

        stream.close()

        # Convert to audio array
        if frames:
            audio = np.frombuffer(b''.join(frames), dtype=np.int16)
            return audio.astype(np.float32) / 32768.0
        return None

    def transcribe(self, audio):
        """Convert audio to text using Whisper"""
        if audio is None:
            return ""

        print("Transcribing...")
        result = self.model.transcribe(audio, language=config['asr']['language'])
        text = result["text"].strip()
        confidence = 1.0 - (sum(seg.get("no_speech_prob", 0.0) for seg in result.get("segments", [])) / max(len(result.get("segments", [])), 1))
        return text, confidence


# Test it
if __name__ == "__main__":
    asr = SpeechRecognizer()

    audio = asr.listen()
    text = asr.transcribe(audio)
    print(f"\nFinal text: {text}")
