import os, datetime, sqlite3, tempfile, uuid, logging
from pathlib import Path
from typing import Optional

import openai, boto3
from pydub import AudioSegment
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import uvicorn

from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
    AudioMessage,
)
from linebot.v3.messaging.api_client import ApiClient
from linebot.v3.messaging.configuration import Configuration
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

from gpt_chat import ask_openai, is_over_token_quota, is_user_whitelisted
from generate_image_bytes import generate_image_bytes
from image_uploader_r2 import upload_image_to_r2
from style_prompt import wrap_as_rina

load_dotenv()

# ---------------------------
# FastAPI & LINE 基本設定
# ---------------------------
app = FastAPI()
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

config = Configuration(access_token=os.getenv("LINE_ACCESS_TOKEN"))
api_client = ApiClient(configuration=config)
line_bot_api = MessagingApi(api_client=api_client)

# ---------------------------
# DB 初始化
# ---------------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    msg_count INTEGER DEFAULT 0,
    is_paid INTEGER DEFAULT 0,
    free_count INTEGER DEFAULT 3,
    paid_until TEXT DEFAULT NULL
)
"""
)
conn.commit()

# ---------------------------
# Cloudflare R2 & OpenAI TTS
# ---------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")

session = boto3.session.Session()
r2_client = session.client(
    "s3",
    endpoint_url=os.getenv("R2_ENDPOINT"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("R2_SECRET_KEY"),
)
R2_BUCKET = os.getenv("R2_BUCKET")


def synthesize_speech(text: str, voice: str = "alloy") -> Path:
    """將文字轉成 mp3 檔案並回傳路徑"""
    response = openai.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        format="mp3",
    )
    tmp_path = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.mp3"
    tmp_path.write_bytes(response.content)
    return tmp_path


def upload_to_r2(local_path: Path) -> str:
    """上傳 mp3 到 R2，回傳公開 URL"""
    key = f"audio/{uuid.uuid4()}.mp3"
    r2_client.upload_file(
        str(local_path),
        R2_BUCKET,
        key,
        ExtraArgs={"ACL": "public-read", "ContentType": "audio/mpeg"},
    )
    return f"https://{R2_BUCKET}.r2.dev/{key}"

# ---------------------------
# FastAPI Routes
# ---------------------------
@app.get("/callback")
async def verify_webhook():
    return "OK"


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("x-line-signature")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        return "Invalid signature"
    return "OK"


# ---------------------------
# LINE Message Handler
# ---------------------------

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    user_id = event.source.user_id
    message_text = event.message.text.strip()

    # 取用戶資訊
    cursor.execute("SELECT msg_count, is_paid, free_count, paid_until FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result is None:
        cursor.execute("INSERT INTO users (user_id, msg_count, is_paid, free_count) VALUES (?, ?, ?, ?)",
                       (user_id, 0, 0, 10))
        conn.commit()
        result = (0, 0, 10, None)

    msg_count, is_paid, free_count, paid_until = result

    # 檢查會員期限
    if paid_until:
        today = datetime.datetime.today().date()
        is_paid = 1 if datetime.datetime.strptime(paid_until, "%Y-%m-%d").date() >= today else 0

    # --------------- 指令區 ---------------
    if message_text.startswith("/朗讀"):
        speak_content = message_text.replace("/朗讀", "").strip() or "你好，我是晴子醬！"
        if is_user_whitelisted(user_id) or is_paid or free_count > 0:
            try:
                tmp_file = synthesize_speech(speak_content)
                audio_url = upload_to_r2(tmp_file)
                duration_ms = len(AudioSegment.from_file(tmp_file))

                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            AudioMessage(original_content_url=audio_url, duration=duration_ms)
                        ],
                    )
                )

                if not is_user_whitelisted(user_id) and not is_paid:
                    cursor.execute("UPDATE users SET free_count = free_count - 1 WHERE user_id=?", (user_id,))
                    conn.commit()
                return
            except Exception as e:
                logging.exception("TTS error: %s", e)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="語音生成失敗了，晴子醬稍後再試🥺")],
                    )
                )
                return
        else:
            response = "你已經用完免費體驗次數囉 🥺\n請輸入 `/購買` 開通晴子醬戀愛方案 💖"
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=response)],
                )
            )
            return

    # 其餘指令保持原邏輯（省略，請在此區塊上方插入你的原 /購買、/畫圖 等邏輯）
    # ...（原內容省略，需自行合併）


# ---------------------------
# Uvicorn 入口
# ---------------------------
if __name__ == "__main__":
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    uvicorn.run(
        "main_v1_7:app",  # 注意: 檔名改了
        host="0.0.0.0",
        port=8000,
        log_level="warning",
    )
