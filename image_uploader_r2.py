import uuid

import boto3
from botocore.client import Config

import config


def upload_image_to_r2(image_bytes):
    access_key = config.R2_ACCESS_TOKEN
    secret_key = config.R2_SECRET_ACCESS_KEY
    endpoint = config.R2_ENDPOINT
    bucket = config.R2_BUCKET_NAME
    public_base = config.R2_PUBLIC_URL
    if not all([access_key, secret_key, endpoint, bucket, public_base]):
        raise EnvironmentError("❌ R2 環境變數未正確設定")

    s3 = boto3.client(
        "s3",
        region_name="auto",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )

    image_name = f"{uuid.uuid4().hex}.jpg"
    key = image_name

    try:
        print(f"[DEBUG] 上傳至 R2: {key}")
        s3.put_object(
            Bucket=bucket, Key=key, Body=image_bytes, ContentType="image/jpeg"
        )
    except Exception as e:
        print(f"[ERROR] R2 上傳失敗: {e}")
        raise RuntimeError(f"Cloudflare R2 上傳失敗: {e}")

    final_url = f"{public_base.rstrip('/')}/{bucket}/{image_name}"
    print(f"[DEBUG] 圖片網址為: {final_url}")
    return final_url


def upload_audio_to_r2(audio_bytes, ext="mp3"):
    """Upload audio data to R2 and return the public URL."""
    access_key = config.R2_ACCESS_TOKEN
    secret_key = config.R2_SECRET_ACCESS_KEY
    endpoint = config.R2_ENDPOINT
    bucket = config.R2_BUCKET_NAME
    public_base = config.R2_PUBLIC_URL
    if not all([access_key, secret_key, endpoint, bucket, public_base]):
        raise EnvironmentError("❌ R2 環境變數未正確設定")

    s3 = boto3.client(
        "s3",
        region_name="auto",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )

    audio_name = f"{uuid.uuid4().hex}.{ext}"
    key = audio_name

    try:
        print(f"[DEBUG] 上傳至 R2: {key}")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=audio_bytes,
            ContentType=f"audio/{ext}",
        )
    except Exception as e:
        print(f"[ERROR] R2 上傳失敗: {e}")
        raise RuntimeError(f"Cloudflare R2 上傳失敗: {e}")

    final_url = f"{public_base.rstrip('/')}/{bucket}/{audio_name}"
    print(f"[DEBUG] 語音網址為: {final_url}")
    return final_url
