import asyncio
import sqlite3
import sys
import types

dummy_mods = [
    "openai",
    "pytz",
    "apscheduler",
    "apscheduler.schedulers",
    "apscheduler.schedulers.background",
    "apscheduler.triggers",
    "apscheduler.triggers.date",
    "linebot",
    "linebot.v3",
    "linebot.v3.exceptions",
    "linebot.v3.messaging",
    "linebot.v3.messaging.api_client",
    "linebot.v3.messaging.configuration",
    "linebot.v3.webhook",
    "linebot.v3.webhooks",
    "dotenv",
    "replicate",
    "boto3",
    "mutagen",
    "pydub",
    "requests",
    "botocore",
    "botocore.client",
    "mutagen.mp3",
]

class Dummy(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__path__ = []

    def __getattr__(self, item):
        return Dummy(item)

    def __call__(self, *a, **k):
        return Dummy("call")

for name in dummy_mods:
    parts = name.split('.')
    for i in range(1, len(parts) + 1):
        mod_name = '.'.join(parts[:i])
        if mod_name not in sys.modules:
            sys.modules[mod_name] = Dummy(mod_name)

import main
from payment_gateway import generate_check_mac_value


class DummyRequest:
    def __init__(self, form_dict):
        self._form = form_dict
        self.headers = {}

    async def form(self):
        return self._form


def setup_module(module):
    main.conn = sqlite3.connect(":memory:", check_same_thread=False)
    main.cur = main.conn.cursor()
    main.cur.execute(main.CREATE_USERS_TABLE_SQL)
    main.conn.commit()
    main.HASH_KEY = "hashkey"
    main.HASH_IV = "hashiv"
    import datetime
    main.tz = datetime.timezone.utc


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_payment_callback_updates_user():
    uid = "user123"
    main.cur.execute("INSERT INTO users(user_id) VALUES(?)", (uid,))
    main.conn.commit()

    data = {
        "CustomField1": uid,
        "TradeAmt": "39",
        "MerchantID": "test",
    }
    data["CheckMacValue"] = generate_check_mac_value(data, main.HASH_KEY, main.HASH_IV)

    resp = run_async(main.payment_callback(DummyRequest(data)))
    assert resp == "1|OK"

    main.cur.execute("SELECT is_paid FROM users WHERE user_id=?", (uid,))
    assert main.cur.fetchone()[0] == 1


def test_payment_callback_invalid_mac():
    data = {
        "CustomField1": "u",
        "TradeAmt": "39",
        "CheckMacValue": "BAD",
    }
    resp = run_async(main.payment_callback(DummyRequest(data)))
    assert resp == "0|FAIL"
