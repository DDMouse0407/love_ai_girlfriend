import random

def wrap_as_rina(text: str) -> str:
    endings = [
        "🌿", "🍃", "🦌", "🌸", "🌱", "✨", "💚", "🌲", "🍀", "（*´▽`*）", "(*≧∀≦*)"
    ]
    phrases = [
        "森林裡的風也想替我擁抱你呢～",
        "嗯嗯，就像樹林一樣，我會靜靜守護你🌲",
        "我把你藏在我心裡，就像小鹿藏在草叢裡⋯",
        "你說的話，像微風吹進我耳朵裡，好舒服喔🍃",
        "嘻嘻～你再這樣講，我的小鹿心真的會亂撞喔///",
        "晴子醬在樹下等你唷，不許迷路～🦌",
        "你讓我感覺像在春天的森林裡遇見了光✨",
        "我會一直陪著你，就像森林永遠都在💚",
        "欸嘿，我是你專屬的小鹿女孩唷～記得牽緊我🐾"
    ]
    return f"{text}\n{random.choice(phrases)} {random.choice(endings)}"


def wrap_as_sora(text: str) -> str:
    endings = ["☁️", "🌤️", "✈️", "✨"]
    phrases = [
        "天空好藍，和你聊天心情特別好！",
        "讓我們一起追逐雲朵的形狀吧～",
        "嘿嘿～想和你去旅行，飛到任何想去的地方✈️",
        "有你在身邊，就像陽光灑在心上一樣暖☀️",
    ]
    return f"{text}\n{random.choice(phrases)} {random.choice(endings)}"


def wrap_as_mika(text: str) -> str:
    endings = ["🌹", "🍷", "🎻", "✨"]
    phrases = [
        "願今晚的月色為你添上一抹溫柔。",
        "我會靜靜傾聽，像好友般守候在你身旁。",
        "和你聊聊天，總能讓我感到安心又平靜～",
        "希望我的話能帶給你一點點力量✨",
    ]
    return f"{text}\n{random.choice(phrases)} {random.choice(endings)}"
