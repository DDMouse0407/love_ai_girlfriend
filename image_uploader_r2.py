import requests
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

def upload_image_to_r2(image_bytes: bytes) -> str:
    token = os.getenv("R2_ACCESS_TOKEN")
    account_id = os.getenv("R2_ACCOUNT_ID")
    bucket = os.getenv("R2_BUCKET_NAME")
    base_url = os.getenv("R2_PUBLIC_BASE_URL")

    filename = f"{uuid.uuid4().hex}.jpg"
    upload_url = f"{os.getenv('R2_UPLOAD_URL_BASE')}/{bucket}/{image_name}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "image/jpeg"
    }

    response = requests.put(upload_url, data=image_bytes, headers=headers)

    if response.status_code == 200:
        return f"{base_url.rstrip('/')}/{filename}"
    else:
        raise Exception(f"R2 上傳失敗: {response.status_code} - {response.text}")
