"""
晴子醬 LINE Bot – V1.8.1  
改進：
1. **Whisper 參數最佳化**  
   * 明確指定 `language="zh"`（繁中）加速推斷並避免誤判  
   * 加入固定 `prompt`：告訴模型「晴子醬與用戶的聊天，請輸出繁體中文」以增補上下文  
   * 保留 `response_format="text"`，保持原本簡潔純文字輸出

其他功能與 V1.8 相同（ASR / TTS / 定時問候）。
"""

import os, datetime, sqlite3, tempfile, uuid, logging, random, asyncio, pytz
from pathlib import Path
from typing import List

import openai, boto3
from pydub import AudioSegment
from apscheduler.schedulers.background import BackgroundScheduler
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
from linebot.v3.webhooks import MessageEvent, TextMessageContent, AudioMessageContent
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
# OpenAI & R2
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

tz = pytz.timezone("Asia/Taipei")

# ---------- 共用工具 ----------

def synthesize_speech(text: str, voice: str = "alloy") -> Path:
    response = openai.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        format="mp3",
    )
    tmp_path = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.mp3"
    tmp_path.write_bytes(response.content)
    return tmp_path


def upload_to_r2(local_path: Path, mime: str = "audio/mpeg") -> str:
    key = f"audio/{uuid.uuid4()}{local_path.suffix}"
    r2_client.upload_file(str(local_path), R2_BUCKET, key, ExtraArgs={"ACL": "public-read", "ContentType": mime})
    return f"https://{R2_BUCKET}.r2.dev/{key}"


PROMPT = "晴子醬與用戶的對話，請輸出繁體中文，口語可愛語氣。"

def transcribe_audio(local_path: Path) -> str:
    """Whisper ASR：最佳化 language & prompt"""
    with local_path.open("rb") as f:
        resp = openai.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text",
            language="zh",           # 指定繁中，加速推斷
            prompt=PROMPT,            # 固定上文，穩定人稱與語氣
            temperature=0             # 最保守，降低漂移
        )
    return resp.strip()

# ---------------------------
# FastAPI Routes
# ---------------------------
@app.get("/callback")
async def verify():
    return "OK"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("x-line-signature")
    body = await request.body()
    try:
        handler.handle(body.decode(), signature)
    except InvalidSignatureError:
        return "Invalid signature"
    return "OK"

# ---------------------------
# LINE Handlers
# ---------------------------

def get_user_state(user_id):
    cursor.execute("SELECT msg_count, is_paid, free_count, paid_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO users (user_id, msg_count, is_paid, free_count) VALUES (?,0,0,10)", (user_id,))
        conn.commit()
        return 0, 0, 10, None
    return row


def decrement_free(user_id):
    cursor.execute("UPDATE users SET free_count = free_count - 1 WHERE user_id=?", (user_id,))
    conn.commit()

async def reply_simple(token, text):
    line_bot_api.reply_message_with_http_info(ReplyMessageRequest(token, [TextMessage(text=text)]))

# Text
@handler.add(MessageEvent, message=TextMessageContent)
def on_text(event):
    handle_logic(event, event.message.text.strip())

# Audio
@handler.add(MessageEvent, message=AudioMessageContent)
def on_audio(event):
    msg_id = event.message.id
    stream = line_bot_api.get_message_content(msg_id)
    tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.m4a"
    with tmp.open("wb") as f:
        for chunk in stream.iter_content():
            f.write(chunk)
    try:
        text = transcribe_audio(tmp)
    except Exception as e:
        logging.exception("ASR error: %s", e)
        asyncio.create_task(reply_simple(event.reply_token, "晴子醬沒聽清楚你的語音🥺"))
        return
    handle_logic(event, text)

# 主邏輯（精簡示例，請自行合併其它指令）

def handle_logic(event, text):
    user_id = event.source.user_id
    msg_count, is_paid, free_cnt, paid_until = get_user_state(user_id)

    if text.startswith("/朗讀"):
        speech = text.replace("/朗讀", "").strip() or "你好，我是晴子醬！"
        if is_user_whitelisted(user_id) or is_paid or free_cnt > 0:
            try:
                mp3 = synthesize_speech(speech)
                url = upload_to_r2(mp3)
                dur = len(AudioSegment.from_file(mp3))
                line_bot_api.reply_message_with_http_info(ReplyMessageRequest(event.reply_token, [AudioMessage(original_content_url=url, duration=dur)]))
                if not (is_user_whitelisted(user_id) or is_paid):
                    decrement_free(user_id)
            except Exception as e:
                logging.exception("TTS error: %s", e)
                asyncio.create_task(reply_simple(event.reply_token, "語音生成失敗，稍後再試🥺"))
        else:
            asyncio.create_task(reply_simple(event.reply_token, "免費次數用完囉，輸入 /購買 開通晴子醬💖"))
        return

    # 其餘一般聊天
    if is_user_whitelisted(user_id) or is_paid or free_cnt > 0:
        reply = wrap_as_rina(ask_openai(text) if not is_over_token_quota() else "晴子醬今天嘴巴破皮...🥺")
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(event.reply_token, [TextMessage(text=reply)]))
        if not (is_user_whitelisted(user_id) or is_paid):
            decrement_free(user_id)
    else:
        asyncio.create_task(reply_simple(event.reply_token, "免費次數用完囉，輸入 /購買 開通晴子醬💖"))

# ---------------------------
# 定時問候
# ---------------------------

greet_morning = ["早安☀️...", "晨光...", "元氣擁抱💪"]
greet_noon = ["午安～", "伸個懶腰", "陪你午餐"]
greet_night = ["晚安🌙", "夜深了", "你更閃耀✨"]

def broadcast(msgs):
    try:
        line_bot_api.broadcast([TextMessage(text=random.choice(msgs))])
    except Exception as e:
        logging.exception("Broadcast error: %s", e)

sched = BackgroundScheduler(timezone=tz)
    sched.add_job(lambda: broadcast_greeting(greet_morning), "cron", hour=7, minute=30)
    sched.add_job(lambda: broadcast_greeting(greet_noon), "cron", hour=11, minute=30)
    sched.add_job(lambda: broadcast_greeting(greet_night), "cron", hour=22, minute=0)
    sched.start()
