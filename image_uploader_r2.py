import os
import uuid
import requests

def upload_image_to_r2(image_bytes):
    bucket = os.getenv("R2_BUCKET")
    base_url = os.getenv("R2_UPLOAD_URL_BASE")
    token = os.getenv("R2_API_TOKEN")

    image_name = f"{uuid.uuid4().hex}.jpg"
    upload_url = f"{base_url}/{bucket}/{image_name}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "image/jpeg"
    }

    response = requests.put(upload_url, data=image_bytes, headers=headers)
    response.raise_for_status()

    return f"{os.getenv('R2_PUBLIC_BASE_URL')}/{image_name}"
