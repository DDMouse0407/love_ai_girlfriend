import requests
import os
from dotenv import load_dotenv
from io import BytesIO

load_dotenv()
API_KEY = os.getenv("SD_API_KEY")

def generate_image_bytes(prompt: str) -> bytes:
    url = "https://stablediffusionapi.com/api/v3/text2img"
    payload = {
        "key": API_KEY,
        "prompt": prompt,
        "negative_prompt": "",
        "width": "512",
        "height": "768",
        "samples": "1",
        "num_inference_steps": "20",
        "guidance_scale": 7.5,
        "safety_checker": "no",
        "webhook": None,
        "seed": None
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        image_url = data["output"][0]
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        return BytesIO(image_response.content).getvalue()
    except Exception as e:
        raise Exception(f"圖片生成失敗: {e}")
