import os
import requests

HF_API_KEY = os.getenv("HF_API_KEY")

def generate_image_bytes(prompt: str) -> bytes:
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt}
    
    print(f"[DEBUG] 發送提示詞：{prompt}")
    response = requests.post(
        "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2",
        headers=headers,
        json=payload
    )
    
    if response.status_code != 200:
        print(f"[ERROR] API 回傳錯誤，狀態碼：{response.status_code}")
        print(f"[ERROR] 回傳內容：{response.text}")
        raise Exception("圖片生成失敗，請稍後再試")

    return response.content
