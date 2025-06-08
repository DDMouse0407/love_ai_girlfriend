import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

def generate_image_bytes(prompt: str) -> bytes:
    api_token = os.getenv("REPLICATE_API_TOKEN")
    if not api_token:
        raise Exception("缺少 REPLICATE_API_TOKEN 環境變數")

    url = "https://api.replicate.com/v1/predictions"
    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }
    data = {
        "version": "db21e45bcb0cf3f06f93b59ab9c0d33e2c5b45f1ffb0b15d6cd9c27a6d096066",  # stable-diffusion-v1.5
        "input": {
            "prompt": prompt
        }
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 201:
        raise Exception(f"Replicate API 建立任務失敗: {response.status_code} {response.text}")

    prediction = response.json()
    prediction_url = f"{url}/{prediction['id']}"

    # 等待任務完成
    for _ in range(30):
        time.sleep(2)
        check = requests.get(prediction_url, headers=headers)
        status = check.json()
        if status["status"] == "succeeded":
            image_url = status["output"][0]
            image_response = requests.get(image_url)
            return image_response.content
        elif status["status"] == "failed":
            raise Exception("Replicate 圖片生成失敗")
    
    raise Exception("Replicate API 等待超時")
