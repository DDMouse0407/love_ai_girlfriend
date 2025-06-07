import requests
import os
import uuid

def upload_image_to_r2(image_bytes, filename=None):
    if not filename:
        filename = f"{uuid.uuid4().hex}.jpg"

    token = os.getenv("R2_ACCESS_TOKEN")
    account_id = os.getenv("R2_ACCOUNT_ID")
    bucket_name = os.getenv("R2_BUCKET_NAME")
    public_url_base = os.getenv("R2_PUBLIC_URL")

    upload_url = f"https://{account_id}.r2.cloudflarestorage.com/{bucket_name}/{filename}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "image/jpeg"
    }

    response = requests.put(upload_url, headers=headers, data=image_bytes)

    if response.status_code in [200, 201]:
        return f"{public_url_base}/{filename}"
    else:
        raise Exception(f"Upload failed: {response.status_code} - {response.text}")
