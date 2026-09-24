from flask import Flask, request, render_template_string, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

# === 環境変数 ===
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID", "")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# === 設定 ===
POST_INTERVAL = 30
last_post_time = {}
posting_enabled = True

# === データベース初期化 ===
def init_db():
    try:
        conn = sqlite3.connect("board.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                title TEXT DEFAULT '無題',
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        print("✅ DB初期化完了")
    except Exception as e:
        print(f"❌ DB初期化エラー: {e}")

def get_posts(limit=50):
    try:
        conn = sqlite3.connect("board.db")
        c = conn.cursor()
        c.execute("SELECT id, user_name, title, body, created_at FROM posts ORDER BY id DESC LIMIT ?", (limit,))
        posts = c.fetchall()
        conn.close()
        return [{"id": p[0], "name": p[1], "title": p[2], "body": p[3], "time": p[4]} for p in posts]
    except Exception as e:
        print(f"❌ 取得エラー: {e}")
        return []

def add_post(user_id, user_name, title, body):
    try:
        conn = sqlite3.connect("board.db")
        c = conn.cursor()
        now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        c.execute(
            "INSERT INTO posts (user_id, user_name, title, body, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, user_name, title, body, now)
        )
        conn.commit()
        conn.close()
        print(f"✅ 投稿成功: {title}")
        return True
    except Exception as e:
        print(f"❌ 投稿エラー: {e}")
        return False

def delete_post(post_id, user_id, is_admin=False):
    try:
        conn = sqlite3.connect("board.db")
        c = conn.cursor()
        if is_admin:
            c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        else:
            c.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id))
        ok = c.rowcount > 0
        conn.commit()
        conn.close()
        return ok
    except:
        return False

def get_user_name(uid):
    try:
        profile = line_bot_api.get_profile(uid)
        return profile.display_name
    except Exception as e:
        print(f"⚠️ ユーザー名取得エラー: {e}")
        return "投稿者"

def is_admin(uid):
    return bool(ADMIN_USER_ID) and uid == ADMIN_USER_ID

def can_post(uid):
    global last_post_time
    now = datetime.now()
    if uid in last_post_time:
        if now - last_post_time[uid] < timedelta(seconds=POST_INTERVAL):
            return False
    last_post_time[uid] = now
    return True

# === ウェブページ ===
HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>🌐 公開掲示板</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{font-family:sans-serif;max-width:750px;margin:0 auto;padding:20px;background:#e8f4ff}
        h1{text-align:center;color:#2d3748;margin-bottom:20px}
        .post{background:#fff;margin:10px 0;padding:15px;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,0.1)}
        .title{font-weight:bold;color:#2b6cb0;margin-bottom:5px}
        .meta{color:#718096;font-size:0.8em;margin:5px 0 10px}
        .body{line-height:1.6;white-space:pre-wrap}
        .empty{text-align:center;color:#718096;padding:40px}
    </style>
</head>
<body>
    <h1>🌐 公開掲示板</h1>
    {% if posts %}
        {% for p in posts %}
        <div class="post">
            <div class="title">{{p.title}}</div>
            <div class="meta">{{p.name}} ・ {{p.time}}</div>
            <div class="body">{{p.body}}</div>
        </div>
        {% endfor %}
    {% else %}
        <p class="empty">まだ投稿がありません</p>
    {% endif %}
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, posts=get_posts())

@app.route("/callback", methods=["POST"])
def callback():
    sig = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, sig)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global posting_enabled
    uid = event.source.user_id
    txt = event.message.text.strip()
    is_adm = is_admin(uid)

    if txt.startswith("/投稿 "):
        if not posting_enabled and not is_adm:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔕 現在投稿を停止しています"))
            return
        if not can_post(uid) and not is_adm:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⏳ 少し時間をおいて投稿してください"))
            return

        content = txt[4:].strip()
        if "｜" in content:
            title, body = content.split("｜", 1)
        else:
            title = "無題"
            body = content
        body = body.strip()
        if not body:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 内容が空です\n例：/投稿 タイトル｜本文"))
            return

        name = get_user_name(uid)
        if add_post(uid, name, title.strip(), body):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"✅ 投稿完了！\n【{title}】\n{name}さん\n\nhttps://line-bot-7jd4.onrender.com/")
            )
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 投稿に失敗しました。しばらくしてから再試行してください"))
        return

    if txt.startswith("/削除 "):
        try:
            pid = int(txt[4:].strip())
        except:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 番号を指定してください"))
            return
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🗑️ 削除しました" if delete_post(pid, uid, is_adm) else "❌ 削除できません")
        )
        return

    if is_adm:
        if txt == "/投稿停止":
            posting_enabled = False
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔕 投稿停止"))
            return
        if txt == "/投稿再開":
            posting_enabled = True
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔔 投稿再開"))
            return

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🌐 掲示板\n\n/投稿 タイトル｜内容\n→ 投稿できます！")
    )

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
