import os
import requests
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")

def generate_image_bytes(prompt: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Accept": "application/json"
    }
    payload = {"inputs": prompt}

    print(f"[DEBUG] 發送提示詞：{prompt}")

    try:
        response = requests.post(
            "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1",
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            print("[DEBUG] 圖片生成成功")
            return response.content
        elif response.status_code == 503:
            print("[ERROR] 模型尚未啟動，請稍候幾秒重試")
            raise Exception("模型加載中，請稍後再試")
        elif response.status_code == 401:
            print("[ERROR] API Key 無效，請確認 HF_API_KEY 是否正確")
            raise Exception("API 金鑰錯誤")
        else:
            print(f"[ERROR] API 回傳錯誤，狀態碼：{response.status_code}")
            print(f"[ERROR] 回傳內容：{response.text}")
            raise Exception("圖片生成失敗，請稍後再試")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 圖片生成時發生例外：{e}")
        raise Exception("無法與 Hugging Face API 連線")
