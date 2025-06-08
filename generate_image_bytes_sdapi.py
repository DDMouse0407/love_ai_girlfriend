import os
import requests
from io import BytesIO
from PIL import Image

def generate_image_bytes(prompt: str) -> bytes:
    url = "https://stablediffusionapi.com/api/v4/dreambooth"
    api_key = os.getenv("SD_API_KEY")
    
    payload = {
        "key": api_key,
        "model_id": "midjourney",  # 可改成 realistic-vision 或其他
        "prompt": prompt,
        "negative_prompt": "",
        "width": "512",
        "height": "512",
        "samples": "1",
        "num_inference_steps": "30",
        "guidance_scale": 7.5,
        "seed": None,
        "webhook": None,
        "track_id": None
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    output_url = response.json()["output"][0]
    image_response = requests.get(output_url)
    image_response.raise_for_status()

    return image_response.content
