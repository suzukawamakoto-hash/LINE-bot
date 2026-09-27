from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    MemberJoinedEvent, MemberLeftEvent
)
import os
import re
import time
from collections import defaultdict

app = Flask(__name__)

# 環境変数から取得
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ===== 設定 =====
ADMIN_USER_IDS = ["Uxxxxxx"]  # 管理者のLINE ID（自分のIDを入れる）
MAX_MESSAGES = 5              # 5秒間に5件以上 → スパム判定
TIME_WINDOW = 5
BAN_KEYWORDS = ["荒らし", "宣伝", "怪しいURL"]  # 検知ワード
KICK_COOLDOWN = 60            # キックは1分に1回まで
# =================

# 状態管理
user_message_times = defaultdict(list)
last_kick_time = 0
banned_users = set()

def is_admin(user_id):
    return user_id in ADMIN_USER_IDS

def check_spam(user_id):
    """連投スパム判定"""
    now = time.time()
    timestamps = user_message_times[user_id]
    timestamps = [t for t in timestamps if now - t < TIME_WINDOW]
    timestamps.append(now)
    user_message_times[user_id] = timestamps
    return len(timestamps) > MAX_MESSAGES

def check_bad_words(text):
    """禁止ワード判定"""
    for word in BAN_KEYWORDS:
        if re.search(re.escape(word), text):
            return True
    return False

def can_kick_now():
    """キック制限：連続実行を防ぐ"""
    global last_kick_time
    now = time.time()
    if now - last_kick_time >= KICK_COOLDOWN:
        last_kick_time = now
        return True
    return False

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    group_id = event.source.group_id

    # 管理者コマンド
    if text.startswith("/"):
        if not is_admin(user_id):
            return
        if text == "/一覧":
            msg = "禁止ユーザー:\n" + "\n".join(banned_users) if banned_users else "登録なし"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        elif text.startswith("/禁止 "):
            banned_users.add(text.split(" ",1)[1])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 追加"))
        elif text.startswith("/解除 "):
            banned_users.discard(text.split(" ",1)[1])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 解除"))
        return

    # 判定
    should_kick = False
    reason = ""

    if user_id in banned_users:
        should_kick = True
        reason = "登録済み禁止ユーザー"
    elif check_spam(user_id):
        should_kick = True
        reason = "連投スパム検知"
    elif check_bad_words(text):
        should_kick = True
        reason = "不適切ワード検知"

    # 実行
    if should_kick and can_kick_now():
        try:
            line_bot_api.kickMember(group_id, user_id)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"🚫 キック: {reason}")
            )
        except Exception as e:
            print(f"キック失敗: {e}")

@handler.add(MemberJoinedEvent)
def on_join(event):
    """新規参加時：即時BANユーザーをチェック"""
    group_id = event.source.group_id
    for member in event.joined.members:
        if member.user_id in banned_users and can_kick_now():
            try:
                line_bot_api.kickMember(group_id, member.user_id)
            except:
                pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
