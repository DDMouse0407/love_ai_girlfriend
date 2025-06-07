import os
import random

def get_sample_image():
    folder = "static/sample_images"
    images = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.png'))]
    if not images:
        return None
    return os.path.join(folder, random.choice(images))
