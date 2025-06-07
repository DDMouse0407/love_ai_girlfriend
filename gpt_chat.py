import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_openai(prompt: str) -> str:
    try:
        completion = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "你是一個講話甜甜的臺灣女孩，請使用繁體中文回應，用溫柔可愛的語氣"},
        {"role": "user", "content": prompt}
    ]
)
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"小熒今天有點當機了… {str(e)}"
