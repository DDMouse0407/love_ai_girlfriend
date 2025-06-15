import json
import requests
import urllib.request
import config

WHITELIST_USER_IDS = config.WHITELIST_USER_IDS
print(f"💡 白名單 ID：{WHITELIST_USER_IDS}")

def ask_openai(prompt: str) -> str:
    try:
        print(f"[DEBUG] 向 OpenAI 發送訊息：{prompt}")

        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "OpenAI-Project": config.OPENAI_PROJECT_ID,
            "Content-Type": "application/json"
        }

        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "你是個可愛、溫柔、帶點撒嬌語氣的虛擬女友，叫晴子醬，講話帶有一點戀愛風格。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7
        }

        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
        res.raise_for_status()
        print("[DEBUG] 回覆成功")
        return res.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"[ERROR] ChatGPT 失敗：{e}")
        return "晴子醬今天有點累，晚點再陪你好不好～🥺"

def is_user_whitelisted(user_id: str) -> bool:
    return user_id in WHITELIST_USER_IDS

def is_over_token_quota():
    try:
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "OpenAI-Project": config.OPENAI_PROJECT_ID
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/dashboard/billing/usage", headers=headers
        )
        with urllib.request.urlopen(req) as resp:
            usage = json.load(resp).get("total_usage", 0) / 100.0

        req = urllib.request.Request(
            "https://api.openai.com/v1/dashboard/billing/subscription",
            headers=headers,
        )
        with urllib.request.urlopen(req) as resp:
            limit = json.load(resp).get("hard_limit_usd", 100)

        return usage > (limit * 0.8)
    except Exception:
        return False
