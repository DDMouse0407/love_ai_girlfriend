from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage
import os
from dotenv import load_dotenv
from gpt_chat import chat_with_girlfriend

# 載入 .env 檔案中的環境變數
load_dotenv()

app = Flask(__name__)

# 初始化 LINE Bot API 與 Webhook Handler
line_bot_api = LineBotApi(os.getenv("LINE_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# Webhook 入口路由
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("Webhook Error:", e)
        abort(400)
    return 'OK'

# 接收訊息事件處理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()

    # 若訊息包含自拍關鍵字，傳送圖片
    if "自拍" in user_msg or "照片" in user_msg or "想看妳" in user_msg:
        image_url = "https://i.imgur.com/Ct0ZcVo.jpg"  # 模擬小熒自拍
        line_bot_api.reply_message(
            event.reply_token,
            ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
        )
        return

    # 否則使用 GPT 回覆對話
    reply_msg = chat_with_girlfriend(user_msg)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_msg)
    )

# Railway 啟動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
