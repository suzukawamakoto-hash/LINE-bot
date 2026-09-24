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

# === データベース ===
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
    except Exception as e:
        print(f"DBエラー: {e}")

def get_posts(limit=50):
    try:
        conn = sqlite3.connect("board.db")
        c = conn.cursor()
        c.execute("SELECT id, user_name, title, body, created_at FROM posts ORDER BY id DESC LIMIT ?", (limit,))
        posts = c.fetchall()
        conn.close()
        return [{"id": p[0], "name": p[1], "title": p[2], "body": p[3], "time": p[4]} for p in posts]
    except:
        return []

def add_post(user_id, user_name, title, body):
    try:
        conn = sqlite3.connect("board.db")
        c = conn.cursor()
        now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        c.execute("""
            INSERT INTO posts (user_id, user_name, title, body, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, user_name, title, body, now))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def delete_post(post_id, user_id, is_admin=False):
    try:
        conn = sqlite3.connect("board.db")
        c = conn.cursor()
        if is_admin:
            c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        else:
            c.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    except:
        return False

def get_user_name(uid):
    try:
        return line_bot_api.get_profile(uid).display_name
    except:
        return "名無しさん"

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
        body{font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;
            max-width:750px;margin:0 auto;padding:20px;background:linear-gradient(135deg,#e8f4ff,#f0fff4);min-height:100vh}
        h1{text-align:center;color:#2d3748;margin-bottom:25px;font-size:1.6em}
        .post{background:#fff;margin-bottom:15px;padding:18px;border-radius:16px;
            box-shadow:0 4px 12px rgba(0,0,0,0.08)}
        .title{font-weight:bold;font-size:1.1em;color:#2b6cb0;margin-bottom:6px}
        .meta{color:#718096;font-size:0.85em;margin-bottom:10px;display:flex;justify-content:space-between}
        .body{color:#2d3748;line-height:1.7;white-space:pre-wrap}
        .empty{text-align:center;color:#718096;padding:50px 20px}
        .info{background:#ebf8ff;border-left:4px solid #3182ce;padding:12px 15px;
            border-radius:8px;margin-bottom:20px;color:#2c5282;font-size:0.9em}
    </style>
</head>
<body>
    <h1>🌐 公開掲示板</h1>
    <div class="info">
        💬 LINE Botから「/投稿 タイトル｜内容」で書き込めます
    </div>
    {% if posts %}
        {% for p in posts %}
        <div class="post">
            <div class="title">{{p.title}}</div>
            <div class="meta"><span>{{p.name}}</span><span>{{p.time}}</span></div>
            <div class="body">{{p.body}}</div>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty">まだ投稿がありません</div>
    {% endif %}
</body>
</html>
"""

@app.route("/")
def index():
    posts = get_posts()
    return render_template_string(HTML, posts=posts)

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
        if not body.strip():
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📝 例：/投稿 タイトル｜内容"))
            return

        name = get_user_name(uid)
        if add_post(uid, name, title.strip(), body.strip()):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"✅ 投稿完了！\n【{title}】\n{name}さん\n\n公開URL：\n{request.url_root}")
            )
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 投稿に失敗しました"))
        return

    if txt.startswith("/削除 "):
        try:
            post_id = int(txt[4:].strip())
        except:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 番号を指定してください"))
            return
        if delete_post(post_id, uid, is_adm):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🗑️ 削除しました"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 削除できません"))
        return

    if is_adm:
        if txt == "/投稿停止":
            posting_enabled = False
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔕 投稿を停止しました"))
            return
        if txt == "/投稿再開":
            posting_enabled = True
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔔 投稿を再開しました"))
            return

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🌐 公開掲示板\n\n/投稿 タイトル｜内容 → 書き込み\n/削除 番号 → 削除")
    )

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
