import os
import requests

def upload_image_to_r2(image_bytes: bytes, filename: str = "output.jpg") -> str:
    # 從環境變數取得公開網址
    public_url = os.getenv("R2_PUBLIC_URL")
    if not public_url:
        raise ValueError("R2_PUBLIC_URL 未設定")

    # 建立上傳目標網址（PUT 到公開 bucket）
    upload_url = f"{public_url.rstrip('/')}/{filename}"

    # 設定正確的 content-type
    headers = {
        "Content-Type": "image/jpeg"
    }

    # 上傳圖片
    response = requests.put(upload_url, data=image_bytes, headers=headers)

    # 檢查是否上傳成功
    if response.status_code != 200:
        raise RuntimeError(f"上傳失敗: {response.status_code} {response.text}")

    return upload_url
