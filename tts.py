import io
import requests
from mutagen.mp3 import MP3

import config


def synthesize_speech(text: str):
    """Generate speech using the ElevenLabs API."""
    url = (
        "https://elevenlabs.io/app/voice-library?voiceId=9lHjugDhwqoxA5MhX0az"
    )
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.6, "similarity_boost": 0.8},
    }
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    audio_bytes = res.content
    try:
        dur = int(MP3(io.BytesIO(audio_bytes)).info.length * 1000)
    except Exception:
        dur = len(text) * 100  # naive fallback
    return audio_bytes, dur
