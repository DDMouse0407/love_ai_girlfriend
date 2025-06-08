from fastapi import FastAPI, Request
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
from linebot.v3.messaging.api_client import ApiClient
from linebot.v3.messaging.configuration import Configuration
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from dotenv import load_dotenv
from gpt_chat import ask_openai, is_over_token_quota, is_user_whitelisted
import uvicorn
import os
import sqlite3
from image_generator import generate_image_bytes
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
    free_count INTEGER DEFAULT 3
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
    if user_id:
        cursor.execute("UPDATE users SET is_paid = 1 WHERE user_id=?", (user_id,))
        conn.commit()
    return {"status": "paid"}

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    user_id = event.source.user_id
    message_text = event.message.text

    cursor.execute("SELECT msg_count, is_paid, free_count FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    if result is None:
        cursor.execute("INSERT INTO users (user_id, msg_count, is_paid, free_count) VALUES (?, ?, ?, ?)", (user_id, 1, 0, 2))
        conn.commit()
        response = wrap_as_rina(ask_openai(message_text))
    else:
        msg_count, is_paid, free_count = result
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

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    user_id = event.source.user_id
    cursor.execute("SELECT is_paid, free_count FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    if result:
        is_paid, free_count = result
        if is_user_whitelisted(user_id) or is_paid or free_count > 0:
            prompt = "a romantic anime girl selfie in forest with green tones and deer theme"
            image_bytes = generate_image_bytes(prompt)
            image_url = upload_image_to_r2(image_bytes)
            reply_text = "哇～你給我看這個是什麼意思呀～我臉紅了啦///"
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=reply_text),
                        ImageMessage(original_content_url=image_url, preview_image_url=image_url)
                    ]
                )
            )
            return

    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="你已經用完免費體驗次數囉 🥺\n請購買晴子醬戀愛方案才能繼續傳圖 💖\n👉 https://p.ecpay.com.tw/97C358E")]
        )
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
