import requests
import os

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

def generate_image_bytes(prompt: str) -> bytes:
    url = "https://api.replicate.com/v1/predictions"
    headers = {
        "Authorization": f"Token {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    json_data = {
        "version": "2286f7a162c66aad8c35c122a9f80f519d9ee20e",
        "input": {"prompt": prompt}
    }

    response = requests.post(url, headers=headers, json=json_data)
    if response.status_code != 201:
        raise Exception(f"Replicate API 建立任務失敗: {response.status_code} {response.text}")

    prediction = response.json()
    prediction_url = prediction["urls"]["get"]

    # 等待模型完成預測
    for _ in range(30):
        res = requests.get(prediction_url, headers=headers)
        output = res.json()
        if output["status"] == "succeeded":
            image_url = output["output"][0]
            break
        elif output["status"] == "failed":
            raise Exception("Replicate 任務失敗")
    else:
        raise Exception("Replicate 任務逾時")

    image_response = requests.get(image_url)
    return image_response.content
