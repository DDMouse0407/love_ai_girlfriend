from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("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")
LINE_CHANNEL_SECRET = os.getenv("3ca0f662b539a5658aa38d172597f9a5")
LINE_ACCESS_TOKEN = os.getenv("HAgY6snmd9E2aFrQlyBLTcbF0br6ygRWMVYp/sSN6hGE2YgOn/uhMpaivlR3eFT082lzLQNvr3USrUFR3uOc4KeGi9zERFYnKaBVro74sBHLewGZ4ysTQ7gAXVN3AMktuqjvvAsC+ay3rTHWCH5utAdB04t89/1O/w1cDnyilFU=")
WHITELIST_USER_IDS = set(filter(None, os.getenv("U563b9f6cdea96af2672ac48816cdb5a7", "").split(",")))
REPLICATE_API_TOKEN = os.getenv("r8_YOEyR1p0cTTUbjTGJIWcqS1fEYdLK960p0pon")
SD_API_KEY = os.getenv("p73tOA7cvCjsrpgQDBiPkapZzB9QgCCua436NrHi0RWUB2CE7lcptY36BpCn")
R2_ACCESS_TOKEN = os.getenv("b5d7c6a0c2e0e27841d1ade901b47fea")
R2_SECRET_ACCESS_KEY = os.getenv("27a163ec4537b565f8a16cc168d59921b40ef7cc8d2c949645a9eb0c701f1e21")
R2_ENDPOINT = os.getenv("https://e5f57ed6bc2c032a711a77b7ebbd5522.r2.cloudflarestorage.com/s985411")
R2_BUCKET_NAME = os.getenv("s985411")
R2_PUBLIC_URL = os.getenv("https://pub-95e2c3d814ae4cdcac65d117b3b06517.r2.dev/")
