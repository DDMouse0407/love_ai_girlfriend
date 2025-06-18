import io
import requests
from mutagen.mp3 import MP3
from pydub import AudioSegment

import config


def _change_speed(sound: AudioSegment, speed: float) -> AudioSegment:
    """Return a new AudioSegment with adjusted playback speed."""
    if speed == 0.1:
        return sound
    new_frame_rate = int(sound.frame_rate * speed)
    altered = sound._spawn(sound.raw_data, overrides={"frame_rate": new_frame_rate})
    return altered.set_frame_rate(sound.frame_rate)


def synthesize_speech(text: str):
    """Generate speech using the ElevenLabs API."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
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
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        audio = _change_speed(audio, config.TTS_SPEED)
        dur = len(audio)
        out = io.BytesIO()
        audio.export(out, format="mp3")
        audio_bytes = out.getvalue()
    except Exception:
        try:
            dur = int(MP3(io.BytesIO(audio_bytes)).info.length * 1000)
        except Exception:
            dur = len(text) * 100  # naive fallback
    return audio_bytes, dur
