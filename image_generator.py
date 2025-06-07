
import os
import random

def get_sample_image():
    sample_dir = 'static/sample_images'
    images = [f for f in os.listdir(sample_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if not images:
        return None
    return os.path.join(sample_dir, random.choice(images))
