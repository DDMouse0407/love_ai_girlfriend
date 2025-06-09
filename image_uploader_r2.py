import os
import uuid
import requests

def upload_image_to_r2(image_bytes):
    bucket = os.getenv("R2_BUCKET_NAME")
    base_url = os.getenv("R2_UPLOAD_URL_BASE")
    token = os.getenv("R2_ACCESS_TOKEN")
    public_base = os.getenv("R2_PUBLIC_URL")

    # 防呆檢查
    if not all([bucket, base_url, token, public_base]):
        raise EnvironmentError("❌ R2 環境變數未正確設定，請檢查 Railway 的 Variables 設定")

    # 產生唯一檔名
    image_name = f"{uuid.uuid4().hex}.jpg"
    upload_url = f"{base_url}/{bucket}/{image_name}"

    print(f"[DEBUG] 上傳網址: {upload_url}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "image/jpeg"
    }

    try:
        response = requests.put(upload_url, data=image_bytes, headers=headers)
        print(f"[DEBUG] 回應狀態碼: {response.status_code}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 上傳 R2 失敗: {e}")
        raise RuntimeError(f"Cloudflare R2 上傳失敗: {e}")

    # 回傳圖片的公開網址
    final_url = f"{public_base}/{image_name}"
    print(f"[DEBUG] 圖片已上傳，公開網址為：{final_url}")
    return final_url
