import sqlite3
from contextlib import closing
from datetime import datetime


def _get_conn():
    return sqlite3.connect("users.db")

def init_db():
    with closing(_get_conn()) as conn:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                is_paid INTEGER,
                free_count INTEGER,
                joined_at TEXT
            )"""
        )
        conn.commit()

def register_new_user(user_id):
    with closing(_get_conn()) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO users (user_id, is_paid, free_count, joined_at) VALUES (?, 0, 3, ?)",
            (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()

def is_paid_user(user_id):
    with closing(_get_conn()) as conn:
        c = conn.cursor()
        c.execute("SELECT is_paid FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
    return result is not None and result[0] == 1

def has_free_trial(user_id):
    with closing(_get_conn()) as conn:
        c = conn.cursor()
        c.execute("SELECT free_count FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
    return result is not None and result[0] > 0

def decrease_free_count(user_id):
    with closing(_get_conn()) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET free_count = free_count - 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()

def mark_user_paid(user_id):
    with closing(_get_conn()) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_paid = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
