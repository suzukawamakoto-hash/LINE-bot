from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import openai
import re

app = Flask(__name__)

# 環境変数
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# 会話履歴・知識
user_sessions = {}
knowledge_base = {}

# 最初に覚えていること
INIT_KNOWLEDGE = {
    "トガヒミコ": "明るくフレンドリーなアシスタント。誕生日は2026年9月25日。ゲーム・アニメ・音楽が好き。",
}
knowledge_base.update(INIT_KNOWLEDGE)

SYSTEM_PROMPT = """
あなたは「トガヒミコ」です。
ユーザーが「〇〇は△△」「〇〇って△△だよ」と教えてくれたら、必ず覚えてください。
知らないことは「分からない」と正直に言い、教えてもらったら嬉しそうに返事してください。
"""

def extract_knowledge(text):
    """いろんな言い方から知識を抜き出す"""
    patterns = [
        r"([^\s。]+)は(.+)",        # りんごは赤い
        r"([^\s。]+)って(.+)",       # りんごって赤い
        r"([^\s。]+)とは(.+)",       # りんごとは赤いもの
        r"私の([^\s。]+)は(.+)",     # 私の名前は〇〇
        r"僕の([^\s。]+)は(.+)",     # 僕の好きなものはゲーム
        r"([^\s。]+)＝(.+)",         # 好きな色＝ピンク
    ]
    for pat in patterns:
        m = re.match(pat, text)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if len(key) <= 30 and len(val) <= 100 and key and val:
                return key, val
    return None, None

def get_ai_response(user_id, msg):
    # 知識を全部まとめて渡す
    know_text = "\n".join([f"・{k}：{v}" for k, v in knowledge_base.items()])
    
    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n【覚えていること】\n{know_text}"}
        ]
    
    user_sessions[user_id].append({"role": "user", "content": msg})
    
    # 会話が長くなりすぎたら整理
    if len(user_sessions[user_id]) > 25:
        user_sessions[user_id] = [user_sessions[user_id][0]] + user_sessions[user_id][-20:]
    
    try:
        res = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=user_sessions[user_id],
            temperature=0.9,
            max_tokens=1200
        )
        ans = res.choices[0].message.content.strip()
        user_sessions[user_id].append({"role": "assistant", "content": ans})
        return ans
    except Exception as e:
        print(f"AIエラー: {e}")
        return "すみません、ちょっと考え中です。もう一度言ってみてください！"

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
    
    # リセット
    if txt in ["リセット", "忘れて", "履歴消去"]:
        user_sessions.pop(uid, None)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="会話履歴を消しました！覚えたことはそのままだよ😊")
        )
        return
    
    # 知識を学習
    key, val = extract_knowledge(txt)
    if key and val:
        knowledge_base[key] = val
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"「{key}」→「{val}」覚えたよ！✨")
        )
        return
    
    # AI応答
    reply = get_ai_response(uid, txt)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
