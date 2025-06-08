import os
import requests

def generate_image_bytes(prompt: str) -> bytes:
    url = "https://stablediffusionapi.com/api/v4/dreambooth"

    payload = {
        "key": os.getenv("SD_API_KEY"),
        "model_id": "anything-v5",
        "prompt": prompt,
        "negative_prompt": "blurry, ugly, disfigured",
        "width": "512",
        "height": "768",
        "samples": "1",
        "num_inference_steps": "30",
        "seed": None,
        "guidance_scale": 7.5,
        "webhook": None,
        "track_id": None
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        image_url = response.json()["output"][0]
        image_response = requests.get(image_url)
        return image_response.content
    except Exception as e:
        raise RuntimeError(f"圖片生成失敗: {e}")
