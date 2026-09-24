from flask import Flask, request, abort, render_template_string
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
from datetime import datetime

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

posts = []  # 掲示板データ

# ウェブページテンプレート
HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>ネット掲示板</title>
    <style>
        body{font-family:sans-serif;max-width:700px;margin:0 auto;padding:20px;background:#f5f5f5}
        h1{text-align:center;color:#222}
        .post{background:white;margin:10px 0;padding:15px;border-radius:10px;box-shadow:0 2px 4px #0001}
        .title{font-weight:bold;font-size:1.1em;color:#2c3e50}
        .meta{color:#777;font-size:0.85em;margin:5px 0}
        .body{margin-top:10px;line-height:1.6}
        .empty{text-align:center;color:#888;padding:30px}
    </style>
</head>
<body>
    <h1>🌐 公開掲示板</h1>
    {% if posts %}
        {% for p in posts|reverse %}
        <div class="post">
            <div class="title">{{p.title}}</div>
            <div class="meta">{{p.name}} ・ {{p.time}}</div>
            <div class="body">{{p.body}}</div>
        </div>
        {% endfor %}
    {% else %}
        <p class="empty">まだ投稿がありません。LINE Botから投稿しよう！</p>
    {% endif %}
</body>
</html>
"""

def get_name(uid):
    try:
        return line_bot_api.get_profile(uid).display_name
    except:
        return "名無し"

# ウェブ公開ページ
@app.route("/")
def index():
    return render_template_string(HTML, posts=posts)

# LINE Webhook
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
def handle(event):
    uid = event.source.user_id
    txt = event.message.text.strip()

    if txt.startswith("/投稿 "):
        content = txt[4:].strip()
        title, body = (content.split("｜", 1) + ["無題"])[:2]
        name = get_name(uid)
        now = datetime.now().strftime("%Y/%m/%d %H:%M")
        posts.append({
            "title": title, "body": body, "name": name, "time": now
        })
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"✅ 投稿しました！\n公開URL：\n{request.url_root}")
        )
        return

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🌐 掲示板Bot\n\n"
            "/投稿 タイトル｜内容\n→ ウェブに公開されます！")
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
