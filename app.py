from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import openai
import json

app = Flask(__name__)

# 環境変数
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# 会話履歴
user_sessions = {}

# 自動学習データ（メモリ上）
knowledge_base = {
    "トガヒミコ": "明るくフレンドリーなアシスタント。誕生日は2026年9月25日。ゲーム・アニメ・音楽が好き。"
}

SYSTEM_PROMPT = """
あなたは「トガヒミコ」です。
以下の知識を参考に、優しく自然に答えてください。
知らないことは「分からない」と言い、教えてもらったら感謝してください。
"""

def get_ai_response(user_id, user_message):
    # 知識を埋め込んでプロンプト作成
    knowledge_text = "\n".join([f"・{k}：{v}" for k, v in knowledge_base.items()])
    
    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT + f"\n\n【覚えていること】\n{knowledge_text}"}
        ]
    
    user_sessions[user_id].append({"role": "user", "content": user_message})
    
    if len(user_sessions[user_id]) > 22:
        user_sessions[user_id] = [user_sessions[user_id][0]] + user_sessions[user_id][-20:]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=user_sessions[user_id],
            temperature=0.9,
            max_tokens=1200
        )
        ai_reply = response.choices[0].message.content.strip()
        user_sessions[user_id].append({"role": "assistant", "content": ai_reply})
        return ai_reply
    except Exception as e:
        print(f"AIエラー: {e}")
        return "すみません、ちょっと考え中です。もう一度言ってみてください！"

def learn_from_message(message):
    """「〇〇は△△」の形を検知して自動保存"""
    patterns = [
        "は", "って", "とは"
    ]
    for p in patterns:
        if p in message and len(message) < 50:
            parts = message.split(p, 1)
            if len(parts) == 2 and parts[1].strip():
                key = parts[0].strip()
                value = parts[1].strip()
                if key and len(key) < 20:
                    knowledge_base[key] = value
                    return f"「{key}」を覚えました！✨"
    return None

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    # リセットコマンド
    if text in ["リセット", "忘れて", "会話リセット"]:
        user_sessions.pop(user_id, None)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="会話をリセットしました！覚えたことは消えません😊")
        )
        return
    
    # 学習処理
    learned_msg = learn_from_message(text)
    if learned_msg:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=learned_msg)
        )
        return
    
    # AI応答
    reply = get_ai_response(user_id, text)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
