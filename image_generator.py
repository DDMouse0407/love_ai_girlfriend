from diffusers import StableDiffusionPipeline
import torch
import uuid
import os

# 初始化模型（只執行一次）
pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float16
).to("cuda" if torch.cuda.is_available() else "cpu")

def generate_image(prompt="cute anime girl blushing"):
    image = pipe(prompt).images[0]
    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join("static", filename)
    os.makedirs("static", exist_ok=True)
    image.save(path)
    return f"https://你的網域/static/{filename}"
