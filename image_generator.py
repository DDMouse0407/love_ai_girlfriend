import os, requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("SD_API_KEY")

def generate_image_bytes_sdapi(prompt: str) -> bytes:
    url = "https://stablediffusionapi.com/api/v3/text2img"  # 以實際 API Endpoint 為準
    headers = {"Authorization": f"Bearer {API_KEY}"}
    payload = {"prompt": prompt}
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    img_url = data["image"]  # 回傳含 image 欄位
    return requests.get(img_url).content
