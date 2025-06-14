import os
import requests
import replicate

import config

if config.REPLICATE_API_TOKEN:
    os.environ.setdefault("REPLICATE_API_TOKEN", config.REPLICATE_API_TOKEN)

# 請確認你已經在 Railway 設定好這個環境變數
# os.environ["REPLICATE_API_TOKEN"] = "你的金鑰"

def generate_image_bytes(prompt: str) -> bytes:
    try:
        output = replicate.run(
            "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",
            input={
                "prompt": prompt,
                "width": 768,
                "height": 768,
                "apply_watermark": False,
                "num_inference_steps": 25
            }
        )
        # output 是 list of URLs，取第一張圖片來下載
        image_url = output[0]
        response = requests.get(image_url)
        response.raise_for_status()
        return response.content

    except Exception as e:
        raise RuntimeError(f"Replicate API 建立任務失敗：{e}")
