"""
晴子醬 LINE Bot – V1.8  
新增功能：
1. **ASR 語音辨識**：支援使用者傳語音訊息，透過 OpenAI Whisper (whisper-1) 轉文字，再走原有聊天邏輯。
2. **早安 / 午安 / 晚安 自動推播**：每天 07:30、12:30、22:00 (Asia/Taipei) 自動推送隨機話題問候。
   * 推播對象為 `users` 資料表內所有使用者。

環境變數新增：  
- `OPENAI_API_KEY`－Whisper 與 TTS 共用  
- 其他 R2 & LINE 參數沿用 V1.7

依賴套件新增：  
```bash
pip install apscheduler==3.* pydub boto3 openai
```
"""

import os, datetime, sqlite3, tempfile, uuid, logging, random
from pathlib import Path
from typing import Optional, List
import asyncio, pytz

import openai, boto3
from pydub import AudioSegment
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, BackgroundTasks
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
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    AudioMessageContent,
)
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
# Cloudflare R2 & OpenAI TTS/ASR
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
    """OpenAI TTS 轉 mp3 檔案"""
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
    r2_client.upload_file(
        str(local_path),
        R2_BUCKET,
        key,
        ExtraArgs={"ACL": "public-read", "ContentType": mime},
    )
    return f"https://{R2_BUCKET}.r2.dev/{key}"


def transcribe_audio(local_path: Path) -> str:
    """Whisper ASR 轉文字"""
    with local_path.open("rb") as f:
        resp = openai.audio.transcriptions.create(model="whisper-1", file=f, response_format="text")
    return resp.strip()


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
# LINE Event Handlers
# ---------------------------

def get_user_state(user_id: str):
    cursor.execute("SELECT msg_count, is_paid, free_count, paid_until FROM users WHERE user_id=?", (user_id,))
    r = cursor.fetchone()
    if r is None:
        cursor.execute("INSERT INTO users (user_id, msg_count, is_paid, free_count) VALUES (?, ?, ?, ?)", (user_id, 0, 0, 10))
        conn.commit()
        return 0, 0, 10, None
    return r


def decrement_free(user_id: str):
    cursor.execute("UPDATE users SET free_count = free_count - 1 WHERE user_id=?", (user_id,))
    conn.commit()


async def reply_text(reply_token: str, text: str):
    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
    )


# ---------- Text ----------
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    process_user_message(event, event.message.text.strip())

# ---------- Audio ----------
@handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio(event):
    message_id = event.message.id
    stream = line_bot_api.get_message_content(message_id)
    tmp_path = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.m4a"
    with tmp_path.open("wb") as f:
        for chunk in stream.iter_content():
            f.write(chunk)
    try:
        transcribed = transcribe_audio(tmp_path)
        process_user_message(event, transcribed)
    except Exception as e:
        logging.exception("ASR error: %s", e)
        asyncio.create_task(reply_text(event.reply_token, "晴子醬聽不清楚，好像沒識別到語音🥺"))


# ---------- 共用聊天邏輯 ----------

def process_user_message(event, message_text: str):
    user_id = event.source.user_id
    msg_count, is_paid, free_count, paid_until = get_user_state(user_id)

    # 會員期限校正
    if paid_until:
        today = datetime.datetime.now(tz).date()
        is_paid = 1 if datetime.datetime.strptime(paid_until, "%Y-%m-%d").date() >= today else 0

    # 指令：/朗讀
    if message_text.startswith("/朗讀"):
        speak_content = message_text.replace("/朗讀", "").strip() or "你好，我是晴子醬！"
        if is_user_whitelisted(user_id) or is_paid or free_count > 0:
            try:
                audio_path = synthesize_speech(speak_content)
                audio_url = upload_to_r2(audio_path)
                duration_ms = len(AudioSegment.from_file(audio_path))
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(event.reply_token, [AudioMessage(original_content_url=audio_url, duration=duration_ms)])
                )
                if not (is_user_whitelisted(user_id) or is_paid):
                    decrement_free(user_id)
                return
            except Exception as e:
                logging.exception("TTS error: %s", e)
                asyncio.create_task(reply_text(event.reply_token, "語音生成失敗了，晴子醬稍後再試🥺"))
                return
        else:
            asyncio.create_task(reply_text(event.reply_token, "你已用完免費體驗次數囉 🥺\n輸入 `/購買` 開通晴子醬戀愛方案 💖"))
            return
    # TODO: 其他指令（/購買、/畫圖 ...）請在此合併原有邏輯

    # 一般聊天
    if is_user_whitelisted(user_id) or is_paid or free_count > 0:
        answer = wrap_as_rina(ask_openai(message_text) if not is_over_token_quota() else "晴子醬今天嘴巴破皮不能講話...🥺")
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(event.reply_token, [TextMessage(text=answer)]))
        if not (is_user_whitelisted(user_id) or is_paid):
            decrement_free(user_id)
    else:
        asyncio.create_task(reply_text(event.reply_token, "你已用完免費體驗次數囉 🥺\n輸入 `/購買` 開通晴子醬戀愛方案 💖"))


# ---------------------------
# APScheduler：早午晚安推播
# ---------------------------

greet_morning: List[str] = [
    "早安☀️！今天天氣很好，記得多補充水分喔！",
    "晨光灑進來了，晴子醬來叫你起床啦～ 🌸",
    "新的一天開始！給你一個元氣擁抱 💪",
]

greet_noon: List[str] = [
    "午安～吃飯了沒？多蔬菜少炸雞喔🍱",
    "忙了一個上午，來伸個懶腰吧 🧘",
    "補充能量的時間到！晴子醬陪你午餐 🍙",
]

greet_night: List[str] = [
    "晚安🌙 今天也辛苦了，床鋪在呼喚你囉！",
    "夜深了，記得放下手機讓眼睛休息 💤",
    "星空很美，但晴子醬覺得你更閃耀 ✨",
]


def broadcast_greeting(messages: List[str]):
    text = random.choice(messages)
    try:
        line_bot_api.broadcast([TextMessage(text=text)])
    except Exception as e:
        logging.exception("Broadcast error: %s", e)


def schedule_jobs():
    sched = BackgroundScheduler(timezone=tz)
    sched.add_job(lambda: broadcast_greeting(greet_morning), "cron", hour=7, minute=30)
    sched.add_job(lambda: broadcast_greeting(greet_noon), "cron", hour=12, minute=00)
    sched.add_job(lambda: broadcast_greeting(greet_night), "cron", hour=22, minute=0)
    sched.start()

schedule_jobs()

# ---------------------------
# Uvicorn Entrypoint
# ---------------------------
if __name__ == "__main__":
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    uvicorn.run("main_v1_8:app", host="0.0.0.0", port=8000, log_level="warning")
