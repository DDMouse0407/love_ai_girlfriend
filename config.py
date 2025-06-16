import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
WHITELIST_USER_IDS = set(filter(None, os.getenv("WHITELIST_USER_IDS", "").split(",")))
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
SD_API_KEY = os.getenv("SD_API_KEY")
R2_ACCESS_TOKEN = os.getenv("R2_ACCESS_TOKEN")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID", "9lHjugDhwqoxA5MhX0az"
)
