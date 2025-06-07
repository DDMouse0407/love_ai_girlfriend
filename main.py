from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
from dotenv import load_dotenv

# 載入 .env 環境變數
load_dotenv()

app = Flask(__name__)

# LINE 官方金鑰
line_bot_api = LineBotApi(os.getenv("LINE_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# Webhook 接收端點
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("Webhook 處理失敗:", e)
        abort(400)
    return 'OK'

# 接收使用者訊息事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text
    reply_msg = f"嗨！我是小熒❤️：你剛剛說「{user_msg}」對嗎？"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_msg)
    )

# Railway 用：監聽 0.0.0.0 + PORT
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
