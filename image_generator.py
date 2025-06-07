import requests

# Hugging Face Spaces 上的圖像生成 API（例如這是 public stable-diffusion）
HF_API_URL = "https://api-inference.huggingface.co/models/prompthero/openjourney"
HF_API_KEY = "你的 Hugging Face Token"

headers = {
    "Authorization": f"Bearer {HF_API_KEY}"
}

def generate_image_url(prompt="a cute anime girlfriend in Ghibli style"):
    payload = {"inputs": prompt}
    response = requests.post(HF_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        # 將回傳圖像以 base64 或 byte stream 儲存為圖片網址（或改上傳至 Imgur）
        with open("static/generated.png", "wb") as f:
            f.write(response.content)
        return "https://你的網域/static/generated.png"
    else:
        return "https://i.imgur.com/qK42fUu.png"  # 回傳預設圖避免錯誤
