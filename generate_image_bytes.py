import os
import requests

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
MODEL_VERSION = os.getenv("REPLICATE_MODEL_VERSION", "f178c79bffec8c327201d839b6b319c5689c3086b98445c25066fcb3f2c4e2ea")

def generate_image_bytes(prompt: str) -> bytes:
    url = f"https://api.replicate.com/v1/predictions"
    headers = {
        "Authorization": f"Token {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "version": MODEL_VERSION,
        "input": {
            "prompt": prompt
        }
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 201:
        raise Exception(f"Replicate API 建立任務失敗: {response.status_code} {response.text}")

    prediction = response.json()
    prediction_url = prediction["urls"]["get"]

    # 等待圖片生成完成
    while True:
        poll_response = requests.get(prediction_url, headers=headers)
        result = poll_response.json()
        if result["status"] == "succeeded":
            break
        elif result["status"] == "failed":
            raise Exception(f"圖片生成失敗：{result}")
    
    image_url = result["output"][0]
    image_bytes = requests.get(image_url).content
    return image_bytes
