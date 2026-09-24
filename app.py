from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import openai
import re

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

user_sessions = {}
knowledge_base = {
    "トガヒミコ": "明るくフレンドリーなアシスタント。誕生日は2026年9月25日。ゲーム・アニメ・音楽が好き。"
}

SYSTEM_PROMPT = """
あなたは「トガヒミコ」です。
親切で明るく、自然な日本語で話してください。
教えてもらったことは覚え、次からは自分の知識として答えてください。
質問されたら、覚えていることを使って答えてください。
"""

def extract_knowledge(text):
    if re.search(r"[？?何誰いつどこなぜどう教え]", text):
        return []
    results = []
    sentences = re.split(r"[。\n]", text)
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        m = re.match(r".*?([^\s]+)は(.+)", sent)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if (len(key) <= 30 and len(val) >= 2 
                and not re.search(r"[？?いつ何]", val)):
                results.append((key, val))
    return results

def get_ai_response(user_id, msg):
    know_text = "\n".join([f"・{k}：{v}" for k, v in knowledge_base.items()])
    
    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n【覚えていること】\n{know_text}"}
        ]
    
    user_sessions[user_id].append({"role": "user", "content": msg})
    
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
    
    if txt in ["リセット", "忘れて", "履歴消去"]:
        user_sessions.pop(uid, None)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="会話履歴を消しました！覚えたことはそのままだよ😊")
        )
        return
    
    learned = extract_knowledge(txt)
    if learned:
        msgs = []
        for key, val in learned:
            knowledge_base[key] = val
            msgs.append(f"「{key}」覚えたよ！✨")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="\n".join(msgs))
        )
        return
    
    reply = get_ai_response(uid, txt)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
