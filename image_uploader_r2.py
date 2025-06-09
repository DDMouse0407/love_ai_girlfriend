import os
import requests
from datetime import datetime

# 讀取環境變數
R2_BUCKET = os.getenv("R2_BUCKET")  # s985411
R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL")  # https://pub-xxxxx.r2.dev
R2_UPLOAD_URL_BASE = os.getenv("R2_UPLOAD_URL_BASE")  # https://xxxx.r2.cloudflarestorage.com
R2_TOKEN = os.getenv("R2_API_TOKEN")  # Cloudflare R2 Token，建議具上傳權限即可

def upload_image_to_r2(image_bytes: bytes, filename_prefix: str = "ai_image") -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.jpg"
    upload_url = f"{R2_UPLOAD_URL_BASE}/{R2_BUCKET}/{filename}"

    headers = {
        "Authorization": f"Bearer {R2_TOKEN}",
        "Content-Type": "image/jpeg"
    }

    res = requests.put(upload_url, data=image_bytes, headers=headers)
    if res.status_code != 200:
        raise Exception(f"R2 圖片上傳失敗：{res.status_code} {res.text}")

    return f"{R2_PUBLIC_BASE_URL}/{filename}"
