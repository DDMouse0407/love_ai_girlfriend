import requests
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

def upload_image_to_r2(image_bytes: bytes) -> str:
    token = os.getenv("R2_ACCESS_TOKEN")
    bucket = os.getenv("R2_BUCKET_NAME")  # 你的 bucket 名稱
    account_id = os.getenv("R2_ACCOUNT_ID")  # 加入 account ID
    base_url = os.getenv("R2_PUBLIC_URL")  # 公開連結使用的 base url

    filename = f"{uuid.uuid4().hex}.jpg"
    upload_url = f"https://{account_id}.r2.cloudflarestorage.com/{bucket}/{filename}"  # 修正重點

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "image/jpeg"
    }

    response = requests.put(upload_url, data=image_bytes, headers=headers)
    if response.status_code == 200:
        return f"{base_url}/{filename}"  # 用公開網址給 LINE
    else:
        raise Exception(f"R2 上傳失敗: {response.status_code} - {response.text}")
