import os, datetime, sqlite3, tempfile, uuid, logging, random, asyncio, pytz
from pathlib import Path

import openai
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

app = FastAPI()
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

config = Configuration(access_token=os.getenv("LINE_ACCESS_TOKEN"))
api_client = ApiClient(configuration=config)
line_bot_api = MessagingApi(api_client=api_client)

tz = pytz.timezone("Asia/Taipei")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------- DB ----------
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY,msg_count INT,is_paid INT,free_count INT,paid_until TEXT)""")
conn.commit(); FREE_QUOTA=10

# ---------- OpenAI ----------
openai.api_key=os.getenv("OPENAI_API_KEY"); PROMPT="晴子醬與用戶的對話，請輸出繁體中文，口語可愛語氣。"

def transcribe_audio(p:Path)->str:
    with p.open("rb") as f:
        return openai.audio.transcriptions.create(model="whisper-1",file=f,response_format="text",language="zh",prompt=PROMPT,temperature=0).strip()

# ---------- Utils ----------

def get_user(uid):
    cur.execute("SELECT msg_count,is_paid,free_count,paid_until FROM users WHERE user_id=?",(uid,));row=cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users(user_id,free_count) VALUES(?,?)",(uid,FREE_QUOTA));conn.commit();return 0,0,FREE_QUOTA,None
    return row

def dec_free(uid): cur.execute("UPDATE users SET free_count=free_count-1 WHERE user_id=?",(uid,));conn.commit()

async def quick_reply(token:str,text:str):
    line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=token,messages=[TextMessage(text=text)]))

# ---------- LINE events ----------
@handler.add(MessageEvent,message=TextMessageContent)
def on_text(e): process(e,e.message.text.strip())

@handler.add(MessageEvent,message=AudioMessageContent)
def on_audio(e):
    tmp=Path(tempfile.gettempdir())/f"{uuid.uuid4()}.m4a";s=line_bot_api.get_message_content(e.message.id)
    with tmp.open("wb") as f:
        for c in s.iter_content(): f.write(c)
    try: txt=transcribe_audio(tmp)
    except Exception as er: logging.exception("ASR:%s",er);asyncio.create_task(quick_reply(e.reply_token,"晴子醬聽不懂這段語音🥺"));return
    process(e,txt)

# ---------- Core ----------

def process(e,text:str):
    uid=e.source.user_id;mc,paid,fc,until=get_user(uid)
    if until and datetime.datetime.strptime(until,"%Y-%m-%d").date()<datetime.datetime.now(tz).date():
        paid=0;cur.execute("UPDATE users SET is_paid=0 WHERE user_id=?",(uid,));conn.commit()

    if text=="/購買":
        link=f"https://p.ecpay.com.tw/97C358E?customField={uid}";asyncio.create_task(quick_reply(e.reply_token,f"點我付款開通晴子醬 💖\n🔗 {link}"));return
    if text=="/狀態查詢":
        if paid:
            days=(datetime.datetime.strptime(until,"%Y-%m-%d").date()-datetime.datetime.now(tz).date()).days if until else 0
            asyncio.create_task(quick_reply(e.reply_token,f"會員剩 {days} 天，到期日 {until} 💎"))
        else: asyncio.create_task(quick_reply(e.reply_token,f"免費體驗剩 {fc} 次，輸入 /購買 解鎖更多功能 ✨"));return

    if text.startswith("/畫圖"):
        prompt=text.replace("/畫圖","",1).strip()
        if not prompt: asyncio.create_task(quick_reply(e.reply_token,"請輸入 /畫圖 主題"));return
        if paid or is_user_whitelisted(uid) or fc>0:
            try:
                url=upload_image_to_r2(generate_image_bytes(prompt))
                line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=e.reply_token,messages=[TextMessage(text=f"晴子醬畫好了～\n主題：{prompt}"),ImageMessage(original_content_url=url,preview_image_url=url)]))
                if not (paid or is_user_whitelisted(uid)): dec_free(uid)
            except Exception as er: logging.exception("/畫圖:%s",er);asyncio.create_task(quick_reply(e.reply_token,"晴子醬畫畫失敗⋯稍後再試🥺"))
        else: asyncio.create_task(quick_reply(e.reply_token,"免費次數用完，輸入 /購買 開通晴子醬💖"));return

    if text.startswith("/朗讀"):
        speech=text.replace("/朗讀","",1).strip() or "你好，我是晴子醬！";asyncio.create_task(quick_reply(e.reply_token,f"(示例) 晴子醬朗讀：{speech}"));return

    if paid or is_user_whitelisted(uid) or fc>0:
        reply=wrap_as_rina(ask_openai(text) if not is_over_token_quota() else "晴子醬今天嘴巴破皮...🥺")
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=e.reply_token,messages=[TextMessage(text=reply)]))
        if not (paid or is_user_whitelisted(uid)): dec_free(uid)
    else: asyncio.create_task(quick_reply(e.reply_token,"免費體驗已用完，輸入 /購買 解鎖晴子醬💖"))

# ---------- FastAPI ----------
@app.post("/callback")
async def callback(req: Request):
    signature = req.headers.get("x-line-signature")
    body: bytes = await req.body()

    try:
        handler.handle(body.decode(), signature)
    except InvalidSignatureError:
        # LINE Channel Secret 不符
        return "Invalid signature"

    return "OK"


@app.get("/health")
async def health():
    """Fly.io health‑check。"""
    return {"status": "ok"}

# ---------- Broadcast ---------- ----------
random_topics=["你今天吃了什麼好吃的～？晴子醬想聽！🍱","工作之餘別忘了抬頭看看雲朵☁️","今天的煩惱交給晴子醬保管，好嗎？🗄️","如果有時光機，你最想回到哪一天？⏳","下雨天的味道是不是有點浪漫？🌧️"]
morning_msgs=["早安☀️！吃早餐了沒？","晨光來敲門，晴子醬來說早安！"]
noon_msgs=["午安～記得抬頭休息眼睛喔！","中場補給時間，吃點好料吧 🍱"]
night_msgs=["晚安🌙 今天辛苦了！","夜深了，放下手機讓眼睛休息 💤"]

sched=BackgroundScheduler(timezone=tz)

def broadcast(msgs):
    try: line_bot_api.broadcast([TextMessage(text=random.choice(msgs))])
    except Exception as e: logging.exception("broadcast:%s",e)

def broadcast_random(): broadcast(random_topics);schedule_next_random()

def schedule_next_random():
    now=datetime.datetime.now(tz);run=now.replace(hour=random.randint(9,22),minute=random.choice([0,30]),second=0,microsecond=0)
    if run<=now: run+=datetime.timedelta(days=1)
    sched.add_job(broadcast_random,trigger=DateTrigger(run_date=run))

# 固定三餐
sched.add_job(lambda:broadcast(morning_msgs),"cron",hour=7,minute=30)
sched.add_job(lambda:broadcast(noon_msgs),"cron",hour=12,minute=30)
sched.add_job(lambda:broadcast(night_msgs),"cron",hour=22,minute=0)

schedule_next_random();sched.add_job(schedule_next_random,"cron",hour=2,minute=0);sched.start()

# ---------- Run ----------
if __name__=="__main__":
    uvicorn.run("main:app",host="0.0.0.0",port=8000,log_level="warning")
