import requests
from io import BytesIO

HUGGING_FACE_API = "https://YOUR_SPACE_NAME.hf.space/api/predict"
HEADERS = {"Content-Type": "application/json"}

def generate_image_bytes(prompt: str) -> bytes:
    payload = {"data": [prompt]}
    response = requests.post(HUGGING_FACE_API, json=payload, headers=HEADERS)
    result = response.json()
    image_url = result["data"][0]  # 圖片 URL
    img_response = requests.get(image_url)
    return img_response.content
