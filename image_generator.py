import random

def get_random_image_url():
    urls = [
        "https://i.imgur.com/QxXgGFE.jpg",
        "https://i.imgur.com/sq7dtKF.jpg",
        "https://i.imgur.com/IjRohfZ.jpg"
    ]
    return random.choice(urls)
