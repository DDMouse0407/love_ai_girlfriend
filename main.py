import asyncio
import datetime
import logging
import random
import sqlite3
import tempfile
import textwrap
import uuid
from pathlib import Path

import openai
import pytz
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
import os
from dotenv import load_dotenv
from payment_gateway import generate_check_mac_value
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    AudioMessage,
    ImageMessage,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.messaging.api_client import ApiClient
from linebot.v3.messaging.configuration import Configuration
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import AudioMessageContent, MessageEvent, TextMessageContent

import config
from generate_image_bytes import generate_image_bytes
from gpt_chat import ask_openai, is_over_token_quota, is_user_whitelisted
from image_uploader_r2 import upload_audio_to_r2, upload_image_to_r2
from personas import DEFAULT_PERSONA, PERSONAS
from tts import synthesize_speech

# ---------------------------
# 基本設定
# ---------------------------
app = FastAPI()
load_dotenv()

MERCHANT_ID = os.getenv("ECPAY_MERCHANT_ID")
HASH_KEY = os.getenv("ECPAY_HASH_KEY")
HASH_IV = os.getenv("ECPAY_HASH_IV")
handler = WebhookHandler(config.LINE_CHANNEL_SECRET)

line_cfg = Configuration(access_token=config.LINE_ACCESS_TOKEN)
api_client = ApiClient(configuration=line_cfg)
line_bot_api = MessagingApi(api_client=api_client)

# Time‑zone & Logger
tz = pytz.timezone("Asia/Taipei")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Supported payment plans mapped by amount
PLANS = {
    39: ("體驗曖昧包", 1),
    99: ("微醺戀人包", 3),
    149: ("夜間心動包", 5),
    189: ("一週戀愛包", 7),
    329: ("深度陪伴包", 14),
    579: ("戀人正式包", 30),
}

# OpenAI
openai.api_key = config.OPENAI_API_KEY
PROMPT = "晴子醬與用戶的對話，請輸出繁體中文，口語可愛語氣。"

# ---------------------------
# 資料庫
# ---------------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()
CREATE_USERS_TABLE_SQL = textwrap.dedent(
    """
    CREATE TABLE IF NOT EXISTS users(
        user_id TEXT PRIMARY KEY,
        msg_count     INT DEFAULT 0,
        is_paid       INT DEFAULT 0,
        free_count    INT DEFAULT 10,
        paid_until    TEXT,
        persona       TEXT DEFAULT 'rina',
        group_personas TEXT
    );
    """
)
cur.execute(CREATE_USERS_TABLE_SQL)
conn.commit()

# 如果舊表缺少 persona 欄位，動態加入
cur.execute("PRAGMA table_info(users)")
cols = [c[1] for c in cur.fetchall()]
if "persona" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN persona TEXT DEFAULT 'rina'")
    conn.commit()
if "group_personas" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN group_personas TEXT")
    conn.commit()

FREE_QUOTA = 10  # 免費可用次數
MONTH_LIMIT = 100  # 月訊息量上限（之後擴充）

# ---------------------------
# 公用函式
# ---------------------------


def get_user(uid: str):
    """抓取／初始化使用者資料"""
    cur.execute(
        "SELECT msg_count, is_paid, free_count, paid_until, persona, group_personas FROM users WHERE user_id=?",
        (uid,),
    )
    row = cur.fetchone()
    if not row:
        cur.execute(
            "INSERT INTO users(user_id, free_count, persona, group_personas) VALUES(?, ?, ?, NULL)",
            (uid, FREE_QUOTA, DEFAULT_PERSONA),
        )
        conn.commit()
        return 0, 0, FREE_QUOTA, None, DEFAULT_PERSONA, None
    return row


def update_msg_stat(uid: str, decr_free: bool = False):
    """統一更新訊息統計與免費額度"""
    if decr_free:
        cur.execute(
            "UPDATE users SET msg_count = msg_count + 1, free_count = free_count - 1 WHERE user_id = ?",
            (uid,),
        )
    else:
        cur.execute(
            "UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (uid,)
        )
    conn.commit()


def dec_free(uid: str):
    cur.execute(
        "UPDATE users SET free_count = free_count - 1 WHERE user_id = ?", (uid,)
    )
    conn.commit()


def transcribe_audio(p: Path) -> str:
    with p.open("rb") as f:
        return openai.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text",
            language="zh",
            prompt=PROMPT,
            temperature=0,
        ).strip()


def _romanticize(text: str) -> str:
    """Return text rewritten in a romantic tone."""
    openings = [
        "親愛的，",
        "嗨～寶貝，",
        "嘿，親親，",
    ]
    bridges = [
        "其實呢，",
        "說真的，",
        "我想告訴你，",
    ]
    endings = [
        "嘿嘿～",
        "嘻嘻～",
        "愛你唷！",
    ]
    return f"{random.choice(openings)}{random.choice(bridges)}{text}，{random.choice(endings)}"


async def quick_reply(reply_token: str, text: str) -> None:
    """Send a simple text reply via LINE."""
    try:
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )
    except Exception as exc:
        logging.exception("quick_reply: %s", exc)


# LINE 事件
# ---------------------------
@handler.add(MessageEvent, message=TextMessageContent)
def on_text(e):
    process(e, e.message.text.strip())


@handler.add(MessageEvent, message=AudioMessageContent)
def on_audio(e):
    uid = e.source.user_id
    tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.m4a"
    stream = line_bot_api.get_message_content(e.message.id)
    with tmp.open("wb") as f:
        for chunk in stream.iter_content():
            f.write(chunk)
    try:
        txt = transcribe_audio(tmp)
    except Exception as er:
        logging.exception("ASR: %s", er)
        display_name = PERSONAS.get(get_user(uid)[4], PERSONAS[DEFAULT_PERSONA])[
            "display"
        ]
        asyncio.create_task(
            quick_reply(e.reply_token, f"{display_name}聽不懂這段語音🥺")
        )
        return
    process(e, txt)


# ---------------------------
# 指令邏輯
# ---------------------------


def process(e, text: str):
    uid = e.source.user_id

    # 讀取目前狀態
    msg_cnt, paid, free_cnt, until, persona, group_personas = get_user(uid)

    # 會員是否過期 → 自動取消
    if (
        paid
        and until
        and datetime.datetime.strptime(until, "%Y-%m-%d").date()
        < datetime.datetime.now(tz).date()
    ):
        paid = 0
        cur.execute("UPDATE users SET is_paid = 0 WHERE user_id = ?", (uid,))
        conn.commit()

    # ---------------------
    # /help
    # ---------------------
    if text == "/help":
        display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
        help_msg = (
            f"✨ {display_name}指令表 ✨\n"
            "--------------------------\n"
            "/畫圖 主題  → AI 畫圖\n"
            f"/朗讀 文字  → {display_name}朗讀（示例）\n"
            "/狀態查詢    → 查看剩餘次數 / 會員到期\n"
            "/購買          → 付款連結\n"
            "/幫我續費      → 快速續費連結\n"
            "/角色 [名稱] → 切換聊天角色\n"
            "/群組 [A B] → 啟用多角色群聊 (輸入 '/群組 取消' 關閉)\n"
            "/help          → 本幫助\n"
            "(系統每日三餐自動提醒)\n"
        )
        asyncio.create_task(quick_reply(e.reply_token, help_msg))
        return

    # ---------------------
    # /購買 /幫我續費
    # ---------------------
    if text in ("/購買", "/幫我續費"):
        link = f"https://rghehlk4bi.cashier.ecpay.com.tw"
        display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
        asyncio.create_task(
            quick_reply(
                e.reply_token, f"點我付款開通 / 續費{display_name} 💖\n🔗 {link}"
            )
        )
        return

    # ---------------------
    # /狀態查詢
    # ---------------------
    if text == "/狀態查詢":
        if paid:
            days_left = (
                (
                    datetime.datetime.strptime(until, "%Y-%m-%d").date()
                    - datetime.datetime.now(tz).date()
                ).days
                if until
                else 0
            )
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
    # /角色
    # ---------------------
    if text.startswith("/角色"):
        name = text.replace("/角色", "", 1).strip()
        if not name:
            choices = "、".join([p["display"] for p in PERSONAS.values()])
            asyncio.create_task(
                quick_reply(
                    e.reply_token,
                    f"目前角色：{PERSONAS[persona]['display']}\n可選擇：{choices}",
                )
            )
            return
        key = None
        for k, v in PERSONAS.items():
            if name in (k, v["display"]):
                key = k
                break
        if not key:
            asyncio.create_task(quick_reply(e.reply_token, "找不到這個角色名稱喔～"))
            return
        cur.execute("UPDATE users SET persona = ? WHERE user_id = ?", (key, uid))
        conn.commit()
        persona = key
        asyncio.create_task(
            quick_reply(e.reply_token, f"已切換為 {PERSONAS[key]['display']}")
        )
        return

    # ---------------------
    # /群組
    # ---------------------
    if text.startswith("/群組"):
        names = text.replace("/群組", "", 1).strip()
        if not names:
            if group_personas:
                display = "、".join(
                    PERSONAS[p]["display"] for p in group_personas.split(",")
                )
                msg = f"目前群組角色：{display}\n輸入 '/群組 角色1 角色2' 重新設定，或 '/群組 取消' 停用"
            else:
                msg = "尚未設定群組角色。輸入 '/群組 角色1 角色2' 啟用"
            asyncio.create_task(quick_reply(e.reply_token, msg))
            return

        if names in ("取消", "關閉"):
            cur.execute(
                "UPDATE users SET group_personas = NULL WHERE user_id = ?", (uid,)
            )
            conn.commit()
            group_personas = None
            asyncio.create_task(quick_reply(e.reply_token, "已停用群組聊天"))
            return

        keys = []
        for name in names.replace("\u3001", " ").replace(",", " ").split():
            for k, v in PERSONAS.items():
                if name in (k, v["display"]):
                    keys.append(k)
                    break
        keys = list(dict.fromkeys(keys))
        if len(keys) < 2:
            asyncio.create_task(
                quick_reply(e.reply_token, "請至少指定兩個有效角色名稱")
            )
            return
        cur.execute(
            "UPDATE users SET group_personas = ? WHERE user_id = ?",
            (",".join(keys), uid),
        )
        conn.commit()
        group_personas = ",".join(keys)
        disp = "、".join(PERSONAS[k]["display"] for k in keys)
        asyncio.create_task(quick_reply(e.reply_token, f"已設定群組角色：{disp}"))
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
            display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
            asyncio.create_task(
                quick_reply(
                    e.reply_token, f"免費次數用完，輸入 /購買 開通{display_name}💖"
                )
            )
            return

        try:
            url = upload_image_to_r2(generate_image_bytes(prompt))
            display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=e.reply_token,
                    messages=[
                        TextMessage(text=f"{display_name}畫好了～\n主題：{prompt}"),
                        ImageMessage(original_content_url=url, preview_image_url=url),
                    ],
                )
            )
            if not (paid or is_user_whitelisted(uid)):
                dec_free(uid)
        except Exception as er:
            logging.exception("/畫圖: %s", er)
            display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
            asyncio.create_task(
                quick_reply(e.reply_token, f"{display_name}畫畫失敗⋯稍後再試🥺")
            )
        return

    # ---------------------
    # /朗讀（示範）
    # ---------------------
    if text.startswith("/朗讀"):
        display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
        speech = text.replace("/朗讀", "", 1).strip() or f"你好，我是{display_name}！"
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
            asyncio.create_task(
                quick_reply(e.reply_token, f"{display_name}朗讀失敗⋯🥺")
            )
        return

    # ---------------------
    # 一般聊天（GPT‑4o）
    # ---------------------
    can_chat = paid or is_user_whitelisted(uid) or free_cnt > 0
    if not can_chat:
        display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
        asyncio.create_task(
            quick_reply(
                e.reply_token, f"免費體驗已用完，輸入 /購買 解鎖{display_name}💖"
            )
        )
        return

    # 取得回覆
    wrappers = {k: v["wrapper"] for k, v in PERSONAS.items()}
    if group_personas:
        reply_parts = []
        for key in group_personas.split(","):
            func = wrappers.get(key, PERSONAS[DEFAULT_PERSONA]["wrapper"])
            if is_over_token_quota():
                disp = PERSONAS.get(key, PERSONAS[DEFAULT_PERSONA])["display"]
                reply = f"{disp}今天嘴巴破皮...🥺"
            else:
                reply = func(ask_openai(text, key))
            reply_parts.append(reply)
        reply_txt = "\n\n".join(reply_parts)
    else:
        wrap_func = wrappers.get(persona, PERSONAS[DEFAULT_PERSONA]["wrapper"])
        if is_over_token_quota():
            display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
            reply_txt = f"{display_name}今天嘴巴破皮...🥺"
        else:
            reply_txt = wrap_func(ask_openai(text, persona))
    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=e.reply_token, messages=[TextMessage(text=reply_txt)]
        )
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


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <h2>AI 女友付款測試</h2>
    <form method="post" action="/ecpay_checkout">
        <button type="submit">我要付款</button>
    </form>
    """


@app.post("/ecpay_checkout", response_class=HTMLResponse)
def checkout():
    order_id = str(uuid.uuid4()).replace("-", "")[:20]
    now = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    params = {
        "MerchantID": MERCHANT_ID,
        "MerchantTradeNo": order_id,
        "MerchantTradeDate": now,
        "PaymentType": "aio",
        "TotalAmount": "50",
        "TradeDesc": "AI 女友戀愛聊天服務",
        "ItemName": "體驗曖昧包(1日)",
        "ReturnURL": "https://你的網址/payment_callback",
        "ClientBackURL": "https://你的網址/success",
        "ChoosePayment": "ALL",
    }

    params["CheckMacValue"] = generate_check_mac_value(params, HASH_KEY, HASH_IV)

    html_form = f"""
    <form id="ecpay_form" method="post" action="https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5">
        {''.join(f'<input type="hidden" name="{k}" value="{v}"/>' for k, v in params.items())}
    </form>
    <script>document.getElementById("ecpay_form").submit();</script>
    """
    return HTMLResponse(content=html_form)


@app.post("/payment_callback")
async def payment_callback(request: Request):
    form_data = await request.form()
    logging.info("ECPay 回傳資料：%s", form_data)

    uid = form_data.get("CustomField1")
    try:
        amt = int(form_data.get("TradeAmt", 0))
    except ValueError:
        amt = 0
    plan = PLANS.get(amt)

    if uid and plan:
        days = plan[1]
        cur.execute("SELECT paid_until FROM users WHERE user_id = ?", (uid,))
        row = cur.fetchone()
        today = datetime.datetime.now(tz).date()
        if row and row[0]:
            current = datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
            base = current if current >= today else today
        else:
            base = today
        new_until = base + datetime.timedelta(days=days)
        cur.execute(
            "UPDATE users SET is_paid = 1, paid_until = ? WHERE user_id = ?",
            (new_until.isoformat(), uid),
        )
        conn.commit()

    return "1|OK"


# ---------------------------
# 廣播與到期提醒
# ---------------------------
random_topics = [
    "你今天吃了什麼好吃的～？我想聽！🍱",
    "工作之餘別忘了抬頭看看雲朵☁️",
    "今天的煩惱交給我保管，好嗎？🗄️",
    "如果有時光機，你最想回到哪一天？⏳",
    "下雨天的味道是不是有點浪漫？🌧️",
]

auto_msgs = {
    "morning": ["早安☀️！吃早餐了沒？", "晨光來敲門，我來說早安！"],
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
    run = now.replace(
        hour=random.randint(9, 22),
        minute=random.choice([0, 30]),
        second=0,
        microsecond=0,
    )
    if run <= now:
        run += datetime.timedelta(days=1)
    sched.add_job(broadcast_random, trigger=DateTrigger(run_date=run))


# 固定三餐提醒
sched.add_job(lambda: broadcast(auto_msgs["morning"]), "cron", hour=7, minute=30)
sched.add_job(lambda: broadcast(auto_msgs["noon"]), "cron", hour=11, minute=30)
sched.add_job(lambda: broadcast(auto_msgs["night"]), "cron", hour=22, minute=0)

# 隨機主題

# ---------------------------
# 會員到期前提醒（每天 10:00）
# ---------------------------


def send_expiry_reminders():
    tomorrow = (
        (datetime.datetime.now(tz) + datetime.timedelta(days=1)).date().isoformat()
    )
    cur.execute(
        "SELECT user_id, paid_until, persona FROM users WHERE is_paid = 1 AND paid_until = ?",
        (tomorrow,),
    )
    for uid, date_str, persona in cur.fetchall():
        display_name = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["display"]
        try:
            line_bot_api.push_message(
                uid,
                [
                    TextMessage(
                        text=f"{display_name}提醒：會員將於 {date_str} 到期～\n輸入 /幫我續費 立即續約 💖"
                    )
                ],
            )
        except Exception as e:
            logging.exception("reminder push: %s", e)


sched.add_job(send_expiry_reminders, "cron", hour=10, minute=0)


@app.on_event("startup")
def start_scheduler() -> None:
    """Start background scheduler when the app starts."""
    schedule_next_random()
    sched.start()
    logging.info("Scheduler started")


@app.on_event("shutdown")
def shutdown_scheduler() -> None:
    """Shutdown background scheduler when the app stops."""
    sched.shutdown()
    logging.info("Scheduler stopped")

# ---------------------------
# 執行 FastAPI
# ---------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="warning")
