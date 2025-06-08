import requests

def generate_image_bytes(prompt: str) -> bytes:
    try:
        print(f"[DEBUG] 發送提示詞：{prompt}")
        response = requests.post(
            "https://anzorq-stable-diffusion-prompt-injector.hf.space/run/predict",
            json={
                "data": [prompt]
            },
            timeout=60
        )
        response.raise_for_status()
        image_url = response.json()["data"][0]
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        return image_response.content
    except Exception as e:
        print(f"[ERROR] 圖片生成失敗：{e}")
        raise Exception("圖片生成失敗，請稍後再試")
