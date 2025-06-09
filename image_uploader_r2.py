import os
import uuid
import boto3
from botocore.client import Config

def upload_image_to_r2(image_bytes):
    access_key = os.getenv("R2_ACCESS_TOKEN")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    endpoint = os.getenv("R2_ENDPOINT")  # ✅ 用戶提供的 Cloudflare S3 Endpoint
    bucket = os.getenv("R2_BUCKET_NAME")
    public_base = os.getenv("R2_PUBLIC_URL")

    # 檢查環境變數是否完整
    if not all([access_key, secret_key, endpoint, bucket, public_base]):
        raise EnvironmentError("❌ R2 環境變數未正確設定")

    # 建立 S3 client
    s3 = boto3.client(
        "s3",
        region_name="auto",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4")
    )

    # 產生唯一圖片名稱
    image_name = f"{uuid.uuid4().hex}.jpg"

    try:
        print(f"[DEBUG] 上傳至 R2: {bucket}/{image_name}")
        s3.put_object(
            Bucket=bucket,
            Key=image_name,
            Body=image_bytes,
            ContentType="image/jpeg"
        )
    except Exception as e:
        print(f"[ERROR] R2 上傳失敗: {e}")
        raise RuntimeError(f"Cloudflare R2 上傳失敗: {e}")

    # ✅ 正確地組合網址（避免多一個 /）
    final_url = f"{public_base.rstrip('/')}/{image_name}"
    print(f"[DEBUG] 圖片網址為: {final_url}")
    return final_url
