import io
import openai
from mutagen.mp3 import MP3


def synthesize_speech(text: str):
    """Generate natural sounding speech using OpenAI TTS."""
    resp = openai.audio.speech.create(
        model="tts-1",
        voice="shimmer",
        input=text,
        response_format="mp3",
    )
    audio_bytes = b"".join(resp.iter_bytes())
    try:
        dur = int(MP3(io.BytesIO(audio_bytes)).info.length * 1000)
    except Exception:
        dur = len(text) * 100  # naive fallback
    return audio_bytes, dur
