import os
import openai
import requests
from dotenv import load_dotenv

load_dotenv()

# 支援從環境變數讀取白名單 ID
WHITELIST_USER_IDS = set(os.getenv("WHITELIST_USER_IDS", "").split(","))

def ask_openai(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "你是個可愛、溫柔、帶點撒嬌語氣的虛擬女友，叫晴子醬，講話帶有一點戀愛風格。"},
                {"role": "user", "content": prompt},
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception:
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
