import requests
import os

def generate_image_bytes(prompt: str) -> bytes:
    url = "https://stablediffusionapi.com/api/v4/dreambooth"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "key": os.getenv("SD_API_KEY"),
        "model_id": "dreamshaper-8-lcm",
        "prompt": prompt,
        "negative_prompt": "blurry, distorted, low quality",
        "width": "512",
        "height": "768",
        "samples": "1",
        "num_inference_steps": "20",
        "guidance_scale": 7.5,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "success" and data.get("output"):
            image_url = data["output"][0]
            img_resp = requests.get(image_url)
            img_resp.raise_for_status()
            return img_resp.content
        else:
            raise RuntimeError(f"圖片生成失敗：{data}")

    except Exception as e:
        raise RuntimeError(f"圖片生成失敗：{e}")
