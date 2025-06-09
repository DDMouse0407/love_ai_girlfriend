import os
import uuid
import boto3
from botocore.client import Config

def upload_image_to_r2(image_bytes):
    access_key = os.getenv("R2_ACCESS_TOKEN")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    endpoint = os.getenv("R2_ENDPOINT")
    bucket = os.getenv("R2_BUCKET_NAME")
    public_base = os.getenv("R2_PUBLIC_URL")

    if not all([access_key, secret_key, endpoint, bucket, public_base]):
        raise EnvironmentError("❌ R2 環境變數未正確設定")

    s3 = boto3.client(
        "s3",
        region_name="auto",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4")
    )

    image_name = f"{uuid.uuid4().hex}.jpg"
    # ✅ 實際上你目前的 R2 是放在 bucket/s985411/ 資料夾下
    r2_key = f"{bucket}/{image_name}"

    try:
        print(f"[DEBUG] 上傳至 R2: {r2_key}")
        s3.put_object(
            Bucket=bucket,
            Key=r2_key,  # ✅ 上傳到正確目錄
            Body=image_bytes,
            ContentType="image/jpeg"
        )
    except Exception as e:
        print(f"[ERROR] R2 上傳失敗: {e}")
        raise RuntimeError(f"Cloudflare R2 上傳失敗: {e}")

    final_url = f"{public_base.rstrip('/')}/{r2_key}"
    print(f"[DEBUG] 圖片網址為: {final_url}")
    return final_url
