import os
import requests
from dotenv import load_dotenv
from openai import OpenAI

# 載入環境變數
load_dotenv()

# 初始化新版 OpenAI 客戶端
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 安全載入白名單（過濾空字串）
WHITELIST_USER_IDS = set(filter(None, os.getenv("WHITELIST_USER_IDS", "").split(",")))
print(f"💡 白名單 ID：{WHITELIST_USER_IDS}")

def ask_openai(prompt: str) -> str:
    try:
        print(f"[DEBUG] 向 OpenAI 發送訊息：{prompt}")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "你是個可愛、溫柔、帶點撒嬌語氣的虛擬女友，叫晴子醬，講話帶有一點戀愛風格。"},
                {"role": "user", "content": prompt},
            ]
        )
        print("[DEBUG] 回覆成功")
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] ChatGPT 失敗：{e}")
        return "晴子醬今天有點累，晚點再陪你好不好～🥺"

def is_user_whitelisted(user_id: str) -> bool:
    return user_id in WHITELIST_USER_IDS

def is_over_token_quota():
    try:
        headers = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}
        usage = requests.get("https://api.openai.com/v1/dashboard/billing/usage", headers=headers).json().get("total_usage", 0) / 100.0
        limit = requests.get("https://api.openai.com/v1/dashboard/billing/subscription", headers=headers).json().get("hard_limit_usd", 100)
        return usage > (limit * 0.8)
    except:
        return False
