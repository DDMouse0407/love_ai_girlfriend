import requests

HUGGING_FACE_SPACE_API = "https://moneymm258.hf.space/api/predict"

def generate_image_bytes(prompt: str) -> bytes:
    payload = {"data": [prompt]}
    response = requests.post(HUGGING_FACE_SPACE_API, json=payload)
    result = response.json()

    # 檢查回傳格式是否正確
    if "data" not in result or not result["data"]:
        raise Exception("Hugging Face Spaces API 回傳格式錯誤")

    image_url = result["data"][0]
    img_response = requests.get(image_url)
    return img_response.content
