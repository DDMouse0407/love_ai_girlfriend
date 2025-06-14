import os, datetime, sqlite3, tempfile, uuid, logging, random, asyncio, pytz
from pathlib import Path
from typing import List

import openai, boto3
from pydub import AudioSegment
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import uvicorn

from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    AudioMessage,
    ImageMessage,
)
from linebot.v3.messaging.api_client import ApiClient
from linebot.v3.messaging.configuration import Configuration
from linebot.v3.webhooks import MessageEvent, TextMessageContent, AudioMessageContent
from linebot.v3.exceptions import InvalidSignatureError

from gpt_chat import ask_openai, is_over_token_quota, is_user_whitelisted
from style_prompt import wrap_as_rina
from generate_image_bytes import generate_image_bytes
from image_uploader_r2 import upload_image_to_r2

load_dotenv()

# --------------------------- 基本設定 ---------------------------
app = FastAPI()
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

config = Configuration(access_token=os.getenv("LINE_ACCESS_TOKEN"))
api_client = ApiClient(configuration=config)
line_bot_api = MessagingApi(api_client=api_client)

tz = pytz.timezone("Asia/Taipei")

# --------------------------- DB ---------------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    msg_count INTEGER DEFAULT 0,
    is_paid INTEGER DEFAULT 0,
    free_count INTEGER DEFAULT 0,
    paid_until TEXT DEFAULT NULL
)
"""
)
conn.commit()

FREE_QUOTA = 10  # 每新用戶免費次數

# --------------------------- OpenAI Whisper & TTS ---------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
PROMPT = "晴子醬與用戶的對話，請輸出繁體中文，口語可愛語氣。"

def transcribe_audio(path: Path) -> str:
    with path.open("rb") as f:
        res = openai.audio.transcriptions.create(model="whisper-1", file=f, response_format="text", language="zh", prompt=PROMPT, temperature=0)
    return res.strip()

# --------------------------- 工具函式 ---------------------------

def get_user(uid):
    cursor.execute("SELECT msg_count,is_paid,free_count,paid_until FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users(user_id,msg_count,is_paid,free_count) VALUES(?,?,?,?)", (uid,0,0,FREE_QUOTA))
        conn.commit()
        return 0,0,FREE_QUOTA,None
    return row

def set_user(**kwargs):
    fields = ",".join([f"{k}=?" for k in kwargs.keys()])
    params = list(kwargs.values())+[kwargs["user_id"]]
    cursor.execute(f"UPDATE users SET {fields} WHERE user_id=?",params)
    conn.commit()

def dec_free(uid):
    cursor.execute("UPDATE users SET free_count = free_count - 1 WHERE user_id=?", (uid,))
    conn.commit()

async def quick_reply(token, text):
    line_bot_api.reply_message_with_http_info(ReplyMessageRequest(token, [TextMessage(text=text)]))

# --------------------------- LINE 事件 ---------------------------
@handler.add(MessageEvent, message=TextMessageContent)
def on_text(evt):
    process_logic(evt, evt.message.text.strip())

@handler.add(MessageEvent, message=AudioMessageContent)
def on_audio(evt):
    stream = line_bot_api.get_message_content(evt.message.id)
    tmp = Path(tempfile.gettempdir())/f"{uuid.uuid4()}.m4a"
    with tmp.open("wb") as f:
        for c in stream.iter_content():
            f.write(c)
    try:
        txt = transcribe_audio(tmp)
    except Exception as e:
        logging.exception("ASR fail: %s",e)
        asyncio.create_task(quick_reply(evt.reply_token, "晴子醬聽不懂這段語音🥺"))
        return
    process_logic(evt, txt)

# --------------------------- 核心邏輯 ---------------------------

def process_logic(evt, text:str):
    uid = evt.source.user_id
    msg_cnt, paid, free_cnt, paid_until = get_user(uid)

    # 會員到期日校正
    if paid_until:
        paid = 1 if datetime.datetime.strptime(paid_until, "%Y-%m-%d").date() >= datetime.datetime.now(tz).date() else 0
        set_user(user_id=uid, is_paid=paid)

    # -------- 指令區 --------
    if text == "/購買":
        link = f"https://p.ecpay.com.tw/97C358E?customField={uid}"
        asyncio.create_task(quick_reply(evt.reply_token, f"點選以下連結付款開通晴子醬戀愛服務 💖\n🔗 {link}"))
        return

    if text == "/狀態查詢":
        if paid:
            days_left = (datetime.datetime.strptime(paid_until, "%Y-%m-%d").date() - datetime.datetime.now(tz).date()).days if paid_until else 0
            asyncio.create_task(quick_reply(evt.reply_token, f"你的會員剩餘 {days_left} 天，到期日 {paid_until} 💎"))
        else:
            asyncio.create_task(quick_reply(evt.reply_token, f"免費體驗剩餘 {free_cnt} 次，輸入 /購買 解鎖更多功能 ✨"))
        return

    if text.startswith("/畫圖"):
        prompt = text.replace("/畫圖", "").strip()
        if not prompt:
            asyncio.create_task(quick_reply(evt.reply_token, "請在 /畫圖 後輸入主題，例如 `/畫圖 森林裡的綠髮少女`"))
            return
        if paid or is_user_whitelisted(uid) or free_cnt>0:
            try:
                img_bytes = generate_image_bytes(prompt)
                url = upload_image_to_r2(img_bytes)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(evt.reply_token,[
                        TextMessage(text=f"晴子醬幫你畫好了～ \n主題：{prompt}"),
                        ImageMessage(original_content_url=url, preview_image_url=url)
                    ])
                )
                if not (paid or is_user_whitelisted(uid)):
                    dec_free(uid)
                return
            except Exception as e:
                logging.exception("/畫圖 err: %s", e)
                asyncio.create_task(quick_reply(evt.reply_token, "晴子醬畫畫失敗⋯稍後再試🥺"))
                return
        else:
            asyncio.create_task(quick_reply(evt.reply_token, "免費體驗次數已用完，輸入 /購買 開通晴子醬💖"))
            return

    if text.startswith("/朗讀"):
        speech = text.replace("/朗讀", "").strip() or "你好，我是晴子醬！"
        asyncio.create_task(quick_reply(evt.reply_token, f"(示例) 晴子醬朗讀：{speech}"))
        return

    # -------- 一般聊天 --------
    if paid or is_user_whitelisted(uid) or free_cnt>0:
        reply = wrap_as_rina(ask_openai(text) if not is_over_token_quota() else "晴子醬今天嘴巴破皮...🥺")
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(evt.reply_token,[TextMessage(text=reply)]))
        if not (paid or is_user_whitelisted(uid)):
            dec_free(uid)
    else:
        asyncio.create_task(quick_reply(evt.reply_token, "免費體驗已用完，輸入 /購買 解鎖晴子醬💖"))

# --------------------------- FastAPI Webhook ---------------------------
@app.get("/callback")
async def ping():
    return "OK"

@app.post("/callback")
async def callback(req: Request):
    signature = req.headers.get("x-line-signature")
    body = await req.body()
    try:
        handler.handle(body.decode(), signature)
    except InvalidSignatureError:
        return "Invalid signature"
    return "OK"

@app.get("/health")
async def health():
    return {"status":"ok"}

# --------------------------- 推播 (三餐 + 隨機) ---------------------------
# (沿用 V1.8.2 內容，保持不變)

random_topics = [
    "你今天吃了什麼好吃的～？晴子醬想聽！🍱",
    "工作之餘別忘了抬頭看看雲朵☁️",
    "今天的煩惱交給晴子醬保管，好嗎？🗄️",
    "如果有時光機，你最想回到哪一天？⏳",
    "下雨天的味道是不是有點浪漫？🌧️",
]

morning_msgs = ["早安☀️！吃早餐了沒？", "晨光來敲門，晴子醬來說早安！"]
noon_msgs = ["午安～記得抬頭休息眼睛喔！", "中場補給時間，吃點好料吧 🍱"]
night_msgs = ["晚安🌙 今天辛苦了！", "夜深了，放下手機讓眼睛休息 💤"]

sched = BackgroundScheduler(timezone=tz)

def broadcast_fixed(msgs):
    try:
        line_bot_api.broadcast([TextMessage(text=random.choice(msgs))])
    except Exception as e:
        logging.exception("Fixed broadcast err: %s", e)
