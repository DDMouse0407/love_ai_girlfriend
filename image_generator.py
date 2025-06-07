import requests
import os
from io import BytesIO

HUGGING_FACE_API = "https://api-inference.huggingface.co/models/YOUR_SPACE_NAME"
HEADERS = {
    "Authorization": f"Bearer {os.getenv('HF_API_KEY')}",
    "Content-Type": "application/json"
}

def generate_image_bytes(prompt: str) -> bytes:
    payload = {"inputs": prompt}
    response = requests.post(HUGGING_FACE_API, headers=HEADERS, json=payload)
    result = response.json()

    if isinstance(result, dict) and result.get("error"):
        raise Exception("Hugging Face API Error: " + result["error"])

    image_url = result[0]["url"] if isinstance(result, list) and "url" in result[0] else None
    if not image_url:
        raise Exception("Image URL not found in Hugging Face response")

    img_response = requests.get(image_url)
    return img_response.content
