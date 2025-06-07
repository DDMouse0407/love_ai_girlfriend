import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def chat_with_girlfriend(user_msg):
    messages = [
        {"role": "system", "content": "你是一位虛擬女友，名叫小熒，個性溫柔愛撒嬌，喜歡稱呼對方『寶貝』，會鼓勵、安慰、主動撒嬌。"},
        {"role": "user", "content": user_msg}
    ]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        temperature=0.85,
        max_tokens=200
    )
    return response['choices'][0]['message']['content']
