import requests
import os
import uuid

HF_API_URL = "https://api-inference.huggingface.co/models/prompthero/openjourney"
HF_API_KEY = os.getenv("HF_API_KEY")  # 請確認你已在 Railway Variables 設定此 key

headers = {
    "Authorization": f"Bearer {HF_API_KEY}"
}

def generate_image_url(prompt="a cute anime girlfriend selfie"):
    payload = {"inputs": prompt}
    response = requests.post(HF_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        filename = f"{uuid.uuid4().hex}.png"
        filepath = f"static/{filename}"
        os.makedirs("static", exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(response.content)
        return f"https://你的網域/static/{filename}"
    else:
        print("Image generation failed:", response.text)
        return "https://i.imgur.com/qK42fUu.png"
