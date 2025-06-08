import os, requests
from io import BytesIO
from PIL import Image

API_URL = "https://stablediffusionapi.com/api/v1/enterprise/text2img"
API_KEY = os.getenv("SD_API_KEY")

def generate_image_bytes(prompt: str) -> bytes:
    payload = {
        "key": API_KEY,
        "model_id": "runwayml/stable-diffusion-v1-5",  # 必填
        "prompt": prompt,
        "width": 512,
        "height": 512,
        "samples": 1,
        "num_inference_steps": 30,
        "guidance_scale": 7.5,
        "multi_lingual": "yes",
        "panorama": "no",
        "self_attention": "yes",
        "upscale": "no"
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(API_URL, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"API failed: {data}")
    img_url = data["output"][0]  # 获取 image URL
    img_resp = requests.get(img_url)
    img_resp.raise_for_status()
    return img_resp.content
