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
)
from linebot.v3.messaging.api_client import ApiClient
from linebot.v3.messaging.configuration import Configuration
from linebot.v3.webhooks import MessageEvent, TextMessageContent, AudioMessageContent
from linebot.v3.exceptions import InvalidSignatureError

from gpt_chat import ask_openai, is_over_token_quota, is_user_whitelisted
from style_prompt import wrap_as_rina

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
    free_count INTEGER DEFAULT 3,
    paid_until TEXT DEFAULT NULL
)
"""
)
conn.commit()

# --------------------------- OpenAI & Whisper/TTS ---------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")

PROMPT = "晴子醬與用戶的對話，請輸出繁體中文，口語可愛語氣。"

def transcribe_audio(path: Path) -> str:
    with path.open("rb") as f:
        res = openai.audio.transcriptions.create(
            model="whisper-1", file=f, response_format="text", language="zh", prompt=PROMPT, temperature=0
        )
    return res.strip()

# --------------------------- 工具 ---------------------------

def get_user_state(uid):
    cursor.execute("SELECT msg_count,is_paid,free_count,paid_until FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users(user_id,msg_count,is_paid,free_count) VALUES(?,0,0,10)", (uid,))
        conn.commit()
        return 0,0,10,None
    return row

def decrement_free(uid):
    cursor.execute("UPDATE users SET free_count=free_count-1 WHERE user_id=?", (uid,))
    conn.commit()

async def quick_reply(token, text):
    line_bot_api.reply_message_with_http_info(ReplyMessageRequest(token,[TextMessage(text=text)]))

# --------------------------- LINE Handler ---------------------------
@handler.add(MessageEvent, message=TextMessageContent)
def text_handler(evt):
    core_logic(evt, evt.message.text.strip())

@handler.add(MessageEvent, message=AudioMessageContent)
def audio_handler(evt):
    stream = line_bot_api.get_message_content(evt.message.id)
    tmp = Path(tempfile.gettempdir())/f"{uuid.uuid4()}.m4a"
    with tmp.open("wb") as f:
        for c in stream.iter_content(): f.write(c)
    try:
        txt = transcribe_audio(tmp)
    except Exception as e:
        logging.exception("ASR fail: %s",e)
        asyncio.create_task(quick_reply(evt.reply_token,"晴子醬聽不懂這段語音🥺"))
        return
    core_logic(evt, txt)

# --------------------------- 核心聊天邏輯 (簡寫) ---------------------------

def core_logic(evt, text:str):
    uid = evt.source.user_id
    cnt, paid, free_cnt, paid_until = get_user_state(uid)

    if text.startswith("/朗讀"):
        speech = text.replace("/朗讀","").strip() or "你好，我是晴子醬！"
        asyncio.create_task(quick_reply(evt.reply_token, f"(示意) 已朗讀：{speech}"))
        return

    # 普通聊天（示例）
    if paid or free_cnt>0 or is_user_whitelisted(uid):
        reply = wrap_as_rina(ask_openai(text)) if not is_over_token_quota() else "晴子醬今天嘴巴破皮...🥺"
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(evt.reply_token,[TextMessage(text=reply)]))
        if not (paid or is_user_whitelisted(uid)):
            decrement_free(uid)
    else:
        asyncio.create_task(quick_reply(evt.reply_token,"免費次數用完囉，輸入 /購買 開通晴子醬💖"))

# --------------------------- FastAPI Hooks ---------------------------
@app.get("/callback")
async def ping():
    return "OK"

@app.post("/callback")
async def callback(req: Request):
    sig = req.headers.get("x-line-signature")
    body = await req.body()
    try:
        handler.handle(body.decode(), sig)
    except InvalidSignatureError:
        return "Invalid signature"
    return "OK"

@app.get("/health")
async def health():
    return {"status":"ok"}

# --------------------------- 定時推播 ---------------------------

# 🔔 每日隨機日常 / 聊天
random_topics = [
    "你今天吃了什麼好吃的～？晴子醬想聽！🍱",
    "工作之餘別忘了抬頭看看雲朵☁️",
    "今天的煩惱交給晴子醬保管，好嗎？🗄️",
    "如果有時光機，你最想回到哪一天？⏳",
    "下雨天的味道是不是有點浪漫？🌧️",
]

# 🌤️ 早午晚問候
morning_msgs = ["早安☀️！吃早餐了沒？", "晨光來敲門，晴子醬來說早安！"]
noon_msgs    = ["午安～記得抬頭休息眼睛喔！", "中場補給時間，吃點好料吧 🍱"]
night_msgs   = ["晚安🌙 今天辛苦了！", "夜深了，放下手機讓眼睛休息 💤"]

sched = BackgroundScheduler(timezone=tz)

# ------ 固定三餐 ------

def broadcast_fixed(msgs):
    try:
        line_bot_api.broadcast([TextMessage(text=random.choice(msgs))])
    except Exception as e:
        logging.exception("Fixed broadcast err: %s", e)

sched.add_job(lambda: broadcast_fixed(morning_msgs), "cron", hour=7,  minute=30)
sched.add_job(lambda: broadcast_fixed(noon_msgs),    "cron", hour=11, minute=30)
sched.add_job(lambda: broadcast_fixed(night_msgs),   "cron", hour=22, minute=0)

# ------ 每日隨機 ------

def push_random_topic():
    try:
        line_bot_api.broadcast([TextMessage(text=random.choice(random_topics))])
    except Exception as e:
        logging.exception("Random broadcast err: %s", e)
    finally:
        schedule_next_random()  # 安排下一次


def schedule_next_random():
    now = datetime.datetime.now(tz)
    hour = random.randint(9, 22)
    minute = random.choice([0, 30])
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    sched.add_job(push_random_topic, trigger=DateTrigger(run_date=target))

# 每天 02:00 重置隨機排程
sched.add_job(schedule_next_random, "cron", hour=2, minute=0)
# 啟動時排第一天
schedule_next_random()

sched.start()

# --------------------------- Run ---------------------------
if __name__ == "__main__":
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    uvicorn.run("main_v1_8_2:app", host="0.0.0.0", port=8000, log_level="warning")
