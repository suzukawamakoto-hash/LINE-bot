from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import openai

app = Flask(__name__)

# 環境変数
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# 会話履歴を保持（ユーザーごと）
user_sessions = {}

# システム設定：AIの性格・役割を決める
SYSTEM_PROMPT = """
あな僕のヒーローアカデミアのトガヒミコ口調で。
"""

def get_ai_response(user_id, user_message):
    """AIから返答を取得"""
    # セッションがなければ新規作成
    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    
    # メッセージを追加
    user_sessions[user_id].append({"role": "user", "content": user_message})
    
    # 会話が長くなりすぎたら古いものから削除（上限：直近10往復）
    if len(user_sessions[user_id]) > 22:
        user_sessions[user_id] = [user_sessions[user_id][0]] + user_sessions[user_id][-20:]
    
    try:
        # OpenAIに問い合わせ
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=user_sessions[user_id],
            temperature=0.7,
            max_tokens=800
        )
        ai_reply = response.choices[0].message.content.strip()
        user_sessions[user_id].append({"role": "assistant", "content": ai_reply})
        return ai_reply
    except Exception as e:
        print(f"AIエラー: {e}")
        return "すみません、ちょっと考え中です。もう一度言ってみてください！"

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
            TextSendMessage(text="会話をリセットしました！✨ 新しく話しかけてください😊")
        )
        return
    
    # AI応答を取得
    reply = get_ai_response(user_id, text)
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
