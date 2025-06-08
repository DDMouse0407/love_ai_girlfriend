import requests

def generate_image_bytes(prompt: str) -> bytes:
    print(f"[DEBUG] 發送提示詞：{prompt}")
    try:
        response = requests.post(
            "https://moneymm258-rina-image-generator.hf.space/run/predict",
            json={"data": [prompt]},
            timeout=120
        )
        response.raise_for_status()
        image_url = response.json()["data"][0]
        image_bytes = requests.get(image_url).content
        return image_bytes
    except Exception as e:
        print(f"[ERROR] 圖片生成失敗：{e}")
        raise Exception("圖片生成失敗，請稍後再試")
