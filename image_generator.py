import requests
import os

HUGGING_FACE_API = "https://moneymm258.hf.space/api/predict"
HEADERS = {"Content-Type": "application/json"}

def generate_image_bytes(prompt: str) -> bytes:
    payload = {
        "data": [prompt]
    }
    response = requests.post(HUGGING_FACE_API, headers=HEADERS, json=payload)
    result = response.json()

    # 安全檢查
    if "data" not in result or not result["data"]:
        raise Exception("Hugging Face response error: no 'data' field")

    image_url = result["data"][0]
    img_response = requests.get(image_url)
    return img_response.content
