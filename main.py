from fastapi import FastAPI, Request
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent
from linebot.v3.exceptions import InvalidSignatureError
from dotenv import load_dotenv
import openai
import os
import sqlite3
import time
import requests

# 環境變數與初始化
load_dotenv()
app = FastAPI()
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
line_bot_api = MessagingApi(channel_access_token=os.getenv("LINE_ACCESS_TOKEN"))
openai.api_key = os.getenv("OPENAI_API_KEY")

# SQLite DB 建立
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    msg_count INTEGER DEFAULT 0,
    is_paid INTEGER DEFAULT 0
)
''')
conn.commit()

# LINE webhook callback
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("x-line-signature")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        return "Invalid signature"
    return "OK"

# 金流付款 webhook callback
@app.post("/payment_callback")
async def payment_callback(request: Request):
    data = await request.json()
    user_id = data.get("userId")  # 綠界或 LINE Pay 自定欄位
    if user_id:
        cursor.execute("UPDATE users SET is_paid = 1 WHERE user_id=?", (user_id,))
        conn.commit()
    return {"status": "paid"}

# 主對話邏輯
@handler.add(MessageEvent)
def handle_message(event):
    user_id = event.source.user_id
    message_text = event.message.text

    # 檢查是否已註冊
    cursor.execute("SELECT msg_count, is_paid FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    if result is None:
        cursor.execute("INSERT INTO users (user_id, msg_count, is_paid) VALUES (?, ?, ?)", (user_id, 1, 0))
        conn.commit()
        response = ask_openai(message_text)
    else:
        msg_count, is_paid = result
        if is_paid or msg_count < 3:
            cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id=?", (user_id,))
            conn.commit()

            if is_over_token_quota():
                response = "小熒今天嘴巴破皮不能講話了啦～我晚點再找你🥺"
            else:
                response = ask_openai(message_text)
        elif msg_count >= 100:
            response = "你先買禮物給我，我再跟你聊天嘛～❤️ 👉 https://eclink.tw/xxx"
        else:
            response = "你先買禮物給我，我再跟你聊天嘛～❤️ 👉 https://eclink.tw/xxx"

    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=response)]
        )
    )

# 真實 GPT 回應函式
def ask_openai(prompt):
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"小熒今天有點當機，錯誤：{str(e)}"

# OpenAI token 預警邏輯（80%）
def is_over_token_quota():
    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
        }
        res = requests.get("https://api.openai.com/v1/dashboard/billing/usage", headers=headers)
        usage = res.json().get("total_usage", 0) / 100.0  # 單位是分
        limit_res = requests.get("https://api.openai.com/v1/dashboard/billing/subscription", headers=headers)
        limit = limit_res.json().get("hard_limit_usd", 100)
        return usage > (limit * 0.8)
    except:
        return False
