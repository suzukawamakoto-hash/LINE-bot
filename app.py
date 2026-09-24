from flask import Flask, request, abort
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

# 掲示板データ保存用
board_posts = []  # 形式：[{"user_id": "...", "user_name": "...", "text": "...", "time": "..."}]

def get_user_name(user_id):
    """ユーザー名取得（簡易版）"""
    try:
        profile = line_bot_api.get_profile(user_id)
        return profile.display_name
    except:
        return "名無しさん"

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
def handle_msg(event):
    uid = event.source.user_id
    txt = event.message.text.strip()

    # === 掲示板：投稿 ===
    if txt.startswith("/掲示板 "):
        content = txt[len("/掲示板 "):].strip()
        if not content:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="📝 投稿内容を入れてね！\n例：/掲示板 今日のおすすめアニメ")
            )
            return
        
        user_name = get_user_name(uid)
        now = datetime.now().strftime("%m/%d %H:%M")
        
        board_posts.append({
            "user_id": uid,
            "user_name": user_name,
            "text": content,
            "time": now
        })
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"✅ 掲示板に投稿しました！\n\n【{user_name}】\n{content}")
        )
        return

    # === 掲示板：一覧表示 ===
    elif txt in ["/掲示板みる", "/掲示板一覧", "/掲示板"]:
        if not board_posts:
            msg = "📭 まだ投稿がありません\n/掲示板 メッセージ で投稿してね！"
        else:
            msg = "📋 掲示板一覧\n" + "―"*1 + "\n"
            for i, post in enumerate(reversed(board_posts[-15:]), 1):
                msg += f"[{i}] {post['user_name']}｜{post['time']}\n{post['text']}\n\n"
            if len(board_posts) > 15:
                msg += f"他 {len(board_posts)-15}件 省略しています"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg)
        )
        return

    # === 掲示板：自分の最新を削除 ===
    elif txt == "/掲示板消す":
        removed = False
        for i in range(len(board_posts)-1, -1, -1):
            if board_posts[i]["user_id"] == uid:
                board_posts.pop(i)
                removed = True
                break
        
        if removed:
            reply = "🗑️ 最後の投稿を削除しました"
        else:
            reply = "📭 削除できる投稿が見つかりません"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return

    # === 通常会話（トガヒミコ）===
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"こんにちは！掲示板Botだよ✨\n\n📝 使い方\n/掲示板 メッセージ → 投稿\n/掲示板みる → 一覧\n/掲示板消す → 自分の最新を削除")
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
