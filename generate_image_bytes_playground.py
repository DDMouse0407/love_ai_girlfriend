# generate_image_bytes_playground.py
import requests

def generate_image_url_playground(prompt: str) -> str:
    print(f"[DEBUG] 發送提示詞至 Playground: {prompt}")
    response = requests.post(
        "https://anzorq-stable-diffusion-prompt-injector.hf.space/api/predict",
        json={"data": [prompt]},
        timeout=60
    )
    if response.status_code == 200:
        data = response.json()
        image_url = data.get("data", [])[0]  # 回傳的是圖片 URL
        if image_url:
            print(f"[DEBUG] Playground 回傳圖片 URL：{image_url}")
            return image_url
        else:
            raise Exception("Playground 未回傳圖片 URL")
    else:
        print(f"[ERROR] Playground API 錯誤：{response.status_code}")
        print(f"[ERROR] 回傳內容：{response.text}")
        raise Exception("Playground 生成圖片失敗")
