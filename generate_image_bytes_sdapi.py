import os
import requests
from io import BytesIO

def generate_image_bytes(prompt: str) -> bytes:
    api_key = os.getenv("SD_API_KEY")

    payload = {
        "key": api_key,
        "prompt": prompt,
        "negative_prompt": None,
        "width": "512",
        "height": "512",
        "samples": "1",
        "num_inference_steps": "30",
        "guidance_scale": 7.5,
        "webhook": None,
        "track_id": None
    }

    response = requests.post(
        "https://stablediffusionapi.com/api/v3/text2img", 
        json=payload
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("output"):
        raise RuntimeError("API 沒有回傳圖片網址")

    image_url = result["output"][0]
    image_response = requests.get(image_url)
    return BytesIO(image_response.content).getvalue()
