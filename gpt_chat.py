
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def chat_with_girlfriend(prompt, history=[]):
    messages = [{"role": "system", "content": "你是一位虛擬女友，名叫小熒，性格溫柔、體貼、愛撒嬌。"},
                *history,
                {"role": "user", "content": prompt}]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        temperature=0.85,
        max_tokens=300
    )
    return response['choices'][0]['message']['content']
