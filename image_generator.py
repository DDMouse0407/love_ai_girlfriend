import os
import requests
from dotenv import load_dotenv

load_dotenv()  # 確保可以讀取 .env 檔案

HF_API_KEY = os.getenv("HF_API_KEY")

def generate_image_bytes(prompt: str) -> bytes:
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt}

    print(f"[DEBUG] 發送提示詞：{prompt}")
    
    try:
        response = requests.post(
            "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1",  # ✅ 修正網址
            headers=headers,
            json=payload,
            timeout=60  # 避免請求掛住
        )

        if response.status_code == 200:
            return response.content
        else:
            print(f"[ERROR] API 回傳錯誤，狀態碼：{response.status_code}")
            print(f"[ERROR] 回傳內容：{response.text}")
            raise Exception("圖片生成失敗，請稍後再試")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 圖片生成時發生例外：{e}")
        raise Exception("無法與 Hugging Face API 連線")
