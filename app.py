from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    MemberJoinedEvent
)
import os
import re
import time
from collections import defaultdict

app = Flask(__name__)

# ===== 環境変数から取得 =====
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ==============================================
# ✅ 自分用に編集する設定エリア
# ==============================================
ADMIN_USER_IDS = ["Ubb14dba8c75028d85c7ada12a3f4177c"]  # ← 自分のLINE IDに置き換え！

MAX_MESSAGES = 8                  # 連投判定：N件以上
TIME_WINDOW = 5                    # 時間幅：N秒以内
KICK_COOLDOWN = 60                 # キックの間隔：N秒に1回まで

BAN_KEYWORDS = [                   # 禁止ワード（自由に追加OK）
    "宣伝",
    "怪しい",
    "無料で稼げる",
    "副業",
    "LINE交換"
]
# ==============================================

# 状態管理
user_message_times = defaultdict(list)
last_kick_time = 0
banned_users = set()

def is_admin(user_id):
    """管理者か判定"""
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
    """キック制限：凍結防止"""
    global last_kick_time
    now = time.time()
    if now - last_kick_time >= KICK_COOLDOWN:
        last_kick_time = now
        return True
    return False

@app.route("/callback", methods=["POST"])
def callback():
    """Webhook受信"""
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """メッセージ処理"""
    user_id = event.source.user_id
    text = event.message.text.strip()
    group_id = event.source.group_id

    # ========== 管理者コマンド ==========
    if text.startswith("/"):
        if not is_admin(user_id):
            return  # 管理者以外は無視

        # メンバー一覧取得
        if text == "/メンバー":
            try:
                member_ids = []
                res = line_bot_api.get_group_member_ids(group_id)
                member_ids.extend(res.member_ids)
                while res.next:
                    res = line_bot_api.get_group_member_ids(
                        group_id, start=res.next
                    )
                    member_ids.extend(res.member_ids)

                msg = f"👥 メンバー数: {len(member_ids)}人\n"
                msg += "\n".join(member_ids[:30])
                if len(member_ids) > 30:
                    msg += f"\n…ほか {len(member_ids)-30}人"

                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text=msg)
                )
            except Exception as e:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"❌ 取得失敗: {str(e)}")
                )
            return

        # 禁止ユーザー一覧
        if text == "/一覧":
            msg = "🚫 禁止ユーザー:\n"
            msg += "\n".join(banned_users) if banned_users else "登録なし"
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=msg)
            )
            return

        # ユーザーをBAN
        if text.startswith("/禁止 "):
            target_id = text.split(" ", 1)[1]
            banned_users.add(target_id)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"✅ BAN追加:\n{target_id}")
            )
            return

        # BAN解除
        if text.startswith("/解除 "):
            target_id = text.split(" ", 1)[1]
            banned_users.discard(target_id)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"✅ BAN解除:\n{target_id}")
            )
            return

        return  # 知らないコマンドは無視

    # ========== 自動判定処理 ==========
    should_kick = False
    reason = ""

    if user_id in banned_users:
        should_kick = True
        reason = "BAN登録済み"
    elif check_spam(user_id):
        should_kick = True
        reason = "連投スパム"
    elif check_bad_words(text):
        should_kick = True
        reason = "禁止ワード"

    # キック実行
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
    """新規参加時：BAN済みを自動キック"""
    group_id = event.source.group_id
    for member in event.joined.members:
        if member.user_id in banned_users and can_kick_now():
            try:
                line_bot_api.kickMember(group_id, member.user_id)
            except Exception as e:
                print(f"参加時キック失敗: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
