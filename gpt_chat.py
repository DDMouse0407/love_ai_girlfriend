from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chat_with_girlfriend(user_msg):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位虛擬女友，名叫小熒，溫柔愛撒嬌，會鼓勵男友。"},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.85,
        max_tokens=200
    )
    return response.choices[0].message.content
