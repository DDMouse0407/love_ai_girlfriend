import datetime
import sqlite3
import tempfile
import uuid
import logging
import random
import asyncio
import pytz
from pathlib import Path

import openai
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from fastapi import FastAPI, Request
import config
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
from style_prompt import wrap_as_rina
from generate_image_bytes import generate_image_bytes
from image_uploader_r2 import upload_image_to_r2, upload_audio_to_r2

# ---------------------------
# 基本設定
# ---------------------------
app = FastAPI()
handler = WebhookHandler(config.LINE_CHANNEL_SECRET)

line_cfg = Configuration(access_token=config.LINE_ACCESS_TOKEN)
api_client = ApiClient(configuration=line_cfg)
line_bot_api = MessagingApi(api_client=api_client)

# Time‑zone & Logger
tz = pytz.timezone("Asia/Taipei")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# OpenAI
openai.api_key = config.OPENAI_API_KEY
PROMPT = "晴子醬與用戶的對話，請輸出繁體中文，口語可愛語氣。"

# ---------------------------
# 資料庫
# ---------------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS users(
        user_id TEXT PRIMARY KEY,
        msg_count     INT DEFAULT 0,
        is_paid       INT DEFAULT 0,
        free_count    INT DEFAULT 10,
        paid_until    TEXT
    )"""
)
conn.commit()

FREE_QUOTA = 10     # 免費可用次數
MONTH_LIMIT = 100   # 月訊息量上限（之後擴充）

# ---------------------------
# 公用函式
# ---------------------------

def get_user(uid: str):
    """抓取／初始化使用者資料"""
    cur.execute("SELECT msg_count, is_paid, free_count, paid_until FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users(user_id, free_count) VALUES(?, ?)", (uid, FREE_QUOTA))
        conn.commit()
        return 0, 0, FREE_QUOTA, None
    return row


def update_msg_stat(uid: str, decr_free: bool = False):
    """統一更新訊息統計與免費額度"""
    if decr_free:
        cur.execute(
            "UPDATE users SET msg_count = msg_count + 1, free_count = free_count - 1 WHERE user_id = ?",
            (uid,),
        )
    else:
        cur.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (uid,))
    conn.commit()


def dec_free(uid: str):
    cur.execute("UPDATE users SET free_count = free_count - 1 WHERE user_id = ?", (uid,))
    conn.commit()


def transcribe_audio(p: Path) -> str:
    with p.open("rb") as f:
        return (
            openai.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
                language="zh",
                prompt=PROMPT,
                temperature=0,
            )
            .strip()
    )


def synthesize_speech(text: str) -> tuple[bytes, int]:
    """Convert text to speech and return audio bytes and duration (ms)."""
    from gtts import gTTS
    from pydub import AudioSegment
    import io

    buf = io.BytesIO()
    gTTS(text=text, lang="zh-tw").write_to_fp(buf)
    buf.seek(0)
    seg = AudioSegment.from_file(buf, format="mp3")
    duration_ms = len(seg)
    out = io.BytesIO()
    seg.export(out, format="mp3")
    return out.getvalue(), duration_ms

async def quick_reply(token: str, text: str):
    """非同步回覆文字，避免阻塞"""
    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(reply_token=token, messages=[TextMessage(text=text)])
    )


# ---------------------------
# LINE 事件
# ---------------------------
@handler.add(MessageEvent, message=TextMessageContent)
def on_text(e):
    process(e, e.message.text.strip())


@handler.add(MessageEvent, message=AudioMessageContent)
def on_audio(e):
    tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.m4a"
    stream = line_bot_api.get_message_content(e.message.id)
    with tmp.open("wb") as f:
        for chunk in stream.iter_content():
            f.write(chunk)
    try:
        txt = transcribe_audio(tmp)
    except Exception as er:
        logging.exception("ASR: %s", er)
        asyncio.create_task(quick_reply(e.reply_token, "晴子醬聽不懂這段語音🥺"))
        return
    process(e, txt)


# ---------------------------
# 指令邏輯
# ---------------------------

def process(e, text: str):
    uid = e.source.user_id

    # 讀取目前狀態
    msg_cnt, paid, free_cnt, until = get_user(uid)

    # 會員是否過期 → 自動取消
    if paid and until and datetime.datetime.strptime(until, "%Y-%m-%d").date() < datetime.datetime.now(tz).date():
        paid = 0
        cur.execute("UPDATE users SET is_paid = 0 WHERE user_id = ?", (uid,))
        conn.commit()

    # ---------------------
    # /help
    # ---------------------
    if text == "/help":
        help_msg = (
            "✨ 晴子醬指令表 ✨\n"
            "--------------------------\n"
            "/畫圖 主題  → AI 畫圖\n"
            "/朗讀 文字  → 晴子朗讀（示例）\n"
            "/狀態查詢    → 查看剩餘次數 / 會員到期\n"
            "/購買          → 付款連結\n"
            "/幫我續費      → 快速續費連結\n"
            "/help          → 本幫助\n"
        )
        asyncio.create_task(quick_reply(e.reply_token, help_msg))
        return

    # ---------------------
    # /購買 /幫我續費
    # ---------------------
    if text in ("/購買", "/幫我續費"):
        link = f"https://p.ecpay.com.tw/97C358E?customField={uid}"
        asyncio.create_task(
            quick_reply(e.reply_token, f"點我付款開通 / 續費晴子醬 💖\n🔗 {link}")
        )
        return

    # ---------------------
    # /狀態查詢
    # ---------------------
    if text == "/狀態查詢":
        if paid:
            days_left = (
                datetime.datetime.strptime(until, "%Y-%m-%d").date() - datetime.datetime.now(tz).date()
            ).days if until else 0
            asyncio.create_task(
                quick_reply(
                    e.reply_token,
                    f"💎 會員剩 {days_left} 天\n到期日：{until}\n月累計訊息：{msg_cnt}",
                )
            )
        else:
            asyncio.create_task(
                quick_reply(
                    e.reply_token,
                    f"免費體驗剩 {free_cnt} 次\n月累計訊息：{msg_cnt}\n輸入 /購買 解鎖更多功能 ✨",
                )
            )
        return

    # ---------------------
    # /畫圖
    # ---------------------
    if text.startswith("/畫圖"):
        prompt = text.replace("/畫圖", "", 1).strip()
        if not prompt:
            asyncio.create_task(quick_reply(e.reply_token, "請輸入 /畫圖 主題"))
            return

        # 權限檢查
        can_use = paid or is_user_whitelisted(uid) or free_cnt > 0
        if not can_use:
            asyncio.create_task(quick_reply(e.reply_token, "免費次數用完，輸入 /購買 開通晴子醬💖"))
            return

        try:
            url = upload_image_to_r2(generate_image_bytes(prompt))
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=e.reply_token,
                    messages=[
                        TextMessage(text=f"晴子醬畫好了～\n主題：{prompt}"),
                        ImageMessage(original_content_url=url, preview_image_url=url),
                    ],
                )
            )
            if not (paid or is_user_whitelisted(uid)):
                dec_free(uid)
        except Exception as er:
            logging.exception("/畫圖: %s", er)
            asyncio.create_task(quick_reply(e.reply_token, "晴子醬畫畫失敗⋯稍後再試🥺"))
        return

    # ---------------------
    # /朗讀（示範）
    # ---------------------
    if text.startswith("/朗讀"):
        speech = text.replace("/朗讀", "", 1).strip() or "你好，我是晴子醬！"
        try:
            audio_bytes, dur = synthesize_speech(speech)
            url = upload_audio_to_r2(audio_bytes)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=e.reply_token,
                    messages=[AudioMessage(original_content_url=url, duration=dur)],
                )
            )
        except Exception as er:
            logging.exception("/朗讀: %s", er)
            asyncio.create_task(quick_reply(e.reply_token, "晴子醬朗讀失敗⋯🥺"))
        return

    # ---------------------
    # 一般聊天（GPT‑4o）
    # ---------------------
    can_chat = paid or is_user_whitelisted(uid) or free_cnt > 0
    if not can_chat:
        asyncio.create_task(quick_reply(e.reply_token, "免費體驗已用完，輸入 /購買 解鎖晴子醬💖"))
        return

    # 取得回覆
    reply_txt = (
        wrap_as_rina(ask_openai(text)) if not is_over_token_quota() else "晴子醬今天嘴巴破皮...🥺"
    )
    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(reply_token=e.reply_token, messages=[TextMessage(text=reply_txt)])
    )

    # 更新統計 & 免費額度
    update_msg_stat(uid, decr_free=not (paid or is_user_whitelisted(uid)))


# ---------------------------
# FastAPI Endpoints
# ---------------------------
@app.post("/callback")
async def callback(req: Request):
    signature = req.headers.get("x-line-signature")
    body: bytes = await req.body()

    try:
        handler.handle(body.decode(), signature)
    except InvalidSignatureError:
        return "Invalid signature"

    return "OK"


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------
# 廣播與到期提醒
# ---------------------------
random_topics = [
    "你今天吃了什麼好吃的～？晴子醬想聽！🍱",
    "工作之餘別忘了抬頭看看雲朵☁️",
    "今天的煩惱交給晴子醬保管，好嗎？🗄️",
    "如果有時光機，你最想回到哪一天？⏳",
    "下雨天的味道是不是有點浪漫？🌧️",
]

auto_msgs = {
    "morning": ["早安☀️！吃早餐了沒？", "晨光來敲門，晴子醬來說早安！"],
    "noon": ["午安～記得抬頭休息眼睛喔！", "中場補給時間，吃點好料吧 🍱"],
    "night": ["晚安🌙 今天辛苦了！", "夜深了，放下手機讓眼睛休息 💤"],
}

sched = BackgroundScheduler(timezone=tz)


def broadcast(msgs):
    try:
        line_bot_api.broadcast([TextMessage(text=random.choice(msgs))])
    except Exception as e:
        logging.exception("broadcast: %s", e)


def broadcast_random():
    broadcast(random_topics)
    schedule_next_random()


def schedule_next_random():
    now = datetime.datetime.now(tz)
    run = now.replace(hour=random.randint(9, 22), minute=random.choice([0, 30]), second=0, microsecond=0)
    if run <= now:
        run += datetime.timedelta(days=1)
    sched.add_job(broadcast_random, trigger=DateTrigger(run_date=run))


# 固定三餐提醒
sched.add_job(lambda: broadcast(auto_msgs["morning"]), "cron", hour=7, minute=30)
sched.add_job(lambda: broadcast(auto_msgs["noon"]), "cron", hour=12, minute=30)
sched.add_job(lambda: broadcast(auto_msgs["night"]), "cron", hour=22, minute=0)

# 隨機主題
schedule_next_random()


# ---------------------------
# 會員到期前提醒（每天 10:00）
# ---------------------------

def send_expiry_reminders():
    tomorrow = (datetime.datetime.now(tz) + datetime.timedelta(days=1)).date().isoformat()
    cur.execute("SELECT user_id, paid_until FROM users WHERE is_paid = 1 AND paid_until = ?", (tomorrow,))
    for uid, date_str in cur.fetchall():
        try:
            line_bot_api.push_message(
                uid,
                [TextMessage(text=f"晴子醬提醒：會員將於 {date_str} 到期～\n輸入 /幫我續費 立即續約 💖")],
            )
        except Exception as e:
            logging.exception("reminder push: %s", e)


sched.add_job(send_expiry_reminders, "cron", hour=10, minute=0)

# 啟動 Scheduler
sched.start()

# ---------------------------
# 執行 FastAPI
# ---------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="warning")
