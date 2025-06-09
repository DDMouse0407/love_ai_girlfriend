from fastapi import FastAPI, Request
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
from linebot.v3.messaging.api_client import ApiClient
from linebot.v3.messaging.configuration import Configuration
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from dotenv import load_dotenv
from gpt_chat import ask_openai, is_over_token_quota, is_user_whitelisted
import uvicorn
import os
import sqlite3
from datetime import datetime, timedelta
from generate_image_bytes import generate_image_bytes
from image_uploader_r2 import upload_image_to_r2
from style_prompt import wrap_as_rina

load_dotenv()

app = FastAPI()
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

config = Configuration(access_token=os.getenv("LINE_ACCESS_TOKEN"))
api_client = ApiClient(configuration=config)
line_bot_api = MessagingApi(api_client=api_client)

conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    msg_count INTEGER DEFAULT 0,
    is_paid INTEGER DEFAULT 0,
    free_count INTEGER DEFAULT 3,
    paid_until TEXT
)
""")
conn.commit()

@app.get("/callback")
async def verify_webhook():
    return "OK"

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("x-line-signature")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        return "Invalid signature"
    return "OK"

@app.post("/payment_callback")
async def payment_callback(request: Request):
    data = await request.json()
    user_id = data.get("userId")
    amount = int(data.get("amount", 0))

    price_to_days = {
        50: 1,
        100: 3,
        150: 5,
        200: 7,
        300: 14,
        500: 30,
        800: 60
    }

    days = price_to_days.get(amount)
    if not days:
        return {"status": "ignored", "reason": "金額不符任何方案"}

    cursor.execute("SELECT paid_until FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    now = datetime.now()
    if result and result[0]:
        current_expiry = datetime.fromisoformat(result[0])
        new_expiry = max(current_expiry, now) + timedelta(days=days)
    else:
        new_expiry = now + timedelta(days=days)

    cursor.execute("""
        INSERT INTO users (user_id, is_paid, paid_until)
        VALUES (?, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            is_paid=1,
            paid_until=excluded.paid_until
    """, (user_id, new_expiry.isoformat()))
    conn.commit()

    return {"status": "success", "paid_until": new_expiry.isoformat()}

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    user_id = event.source.user_id
    message_text = event.message.text.strip()

    cursor.execute("SELECT msg_count, is_paid, free_count, paid_until FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    if result is None:
        cursor.execute("INSERT INTO users (user_id, msg_count, is_paid, free_count, paid_until) VALUES (?, ?, ?, ?, ?)",
                       (user_id, 1, 0, 2, None))
        conn.commit()
        result = (1, 0, 2, None)

    msg_count, is_paid, free_count, paid_until = result

    # 檢查會員是否過期
    if paid_until:
        if datetime.fromisoformat(paid_until) < datetime.now():
            is_paid = 0
            cursor.execute("UPDATE users SET is_paid = 0 WHERE user_id=?", (user_id,))
            conn.commit()

    if message_text.startswith("/畫圖"):
        prompt = message_text.replace("/畫圖", "").strip()
        if not prompt:
            response = "請輸入圖片主題，例如：`/畫圖 森林裡的綠髮女孩`"
        elif is_user_whitelisted(user_id) or is_paid or free_count > 0:
            try:
                print(f"[DEBUG] 開始產生圖片，主題：{prompt}")
                image_bytes = generate_image_bytes(prompt)
                print(f"[DEBUG] 圖片產生成功，準備上傳 R2")
                image_url = upload_image_to_r2(image_bytes)
                print(f"[DEBUG] R2 上傳成功，圖片網址為：{image_url}")

                reply_text = f"晴子醬幫你畫好了～主題是：「{prompt}」🌿"
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(text=reply_text),
                            ImageMessage(original_content_url=image_url, preview_image_url=image_url)
                        ]
                    )
                )

                if not is_user_whitelisted(user_id) and not is_paid:
                    cursor.execute("UPDATE users SET free_count = free_count - 1 WHERE user_id=?", (user_id,))
                    conn.commit()
                return
            except Exception as e:
                print(f"[ERROR] 處理 /畫圖 指令時發生錯誤：{e}")
                response = "晴子醬畫畫的時候不小心迷路了...請稍後再試一次 🥺"
        else:
            response = "你已經用完免費體驗次數囉 🥺\n請購買晴子醬戀愛方案才能繼續畫圖 💖\n👉 https://p.ecpay.com.tw/97C358E"
    else:
        if is_user_whitelisted(user_id):
            cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id=?", (user_id,))
            conn.commit()
            response = wrap_as_rina(ask_openai(message_text)) + "\n（開發者白名單無限制）"
        elif is_paid:
            cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id=?", (user_id,))
            conn.commit()
            if is_over_token_quota():
                response = "晴子醬今天嘴巴破皮不能講話了啦～我晚點再陪你好不好～🥺"
            else:
                response = wrap_as_rina(ask_openai(message_text))
        elif free_count > 0:
            cursor.execute("UPDATE users SET msg_count = msg_count + 1, free_count = free_count - 1 WHERE user_id=?", (user_id,))
            conn.commit()
            response = wrap_as_rina(ask_openai(message_text)) + f"\n（免費體驗剩餘次數：{free_count - 1}）"
        else:
            response = "你已經用完免費體驗次數囉 🥺\n請購買晴子醬戀愛方案才能繼續聊天 💖\n👉 https://p.ecpay.com.tw/97C358E"

    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=response)]
        )
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
