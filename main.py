from flask import Flask, request, abort, send_file
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage
import os
from dotenv import load_dotenv
from gpt_chat import chat_with_girlfriend
from image_generator import get_sample_image

# 載入環境變數
load_dotenv()

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Webhook Error: {e}")
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()

    # 自拍圖觸發詞（你可以改成更自然的關鍵字）
    if "自拍" in user_msg or "照片" in user_msg:
        img_path = get_sample_image()
        if img_path:
            image_url = "https://your-domain.up.railway.app/sample_image"  # 要自行上傳圖片或串 Cloud Storage
            line_bot_api.reply_message(
                event.reply_token,
                ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)
            )
            return
        else:
            reply_msg = "今天的自拍還沒準備好哦～🥺"
    else:
        reply_msg = chat_with_girlfriend(user_msg)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_msg)
    )

# 這個路由可讓你測試 sample 圖片回傳（若有上傳圖片到外部網址才需）
@app.route("/sample_image")
def sample_image():
    path = get_sample_image()
    if not path:
        return "No image", 404
    return send_file(path, mimetype="image/jpeg")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
