from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ===== 自分のLINE IDに書き換え =====
ADMIN_USER_ID = "Ubb14dba8c75028d85c7ada12a3f4177c"

banned_users = set()

# ========== Discord Bot ==========
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

discord_bot = commands.Bot(command_prefix="!", intents=intents)

@discord_bot.event
async def on_ready():
    print(f"✅ Discord Bot 起動: {discord_bot.user}")

@discord_bot.command(name="メンバー")
async def cmd_members(ctx):
    members = [m.name for m in ctx.guild.members if not m.bot]
    await ctx.send(f"👥 メンバー数: {len(members)}人\n" + "\n".join(members[:30]))

@discord_bot.command(name="BAN")
async def cmd_ban(ctx, member: discord.Member = None):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 管理者権限が必要です")
        return
    if not member:
        await ctx.send("❌ 使い方: !BAN @ユーザー名")
        return
    await ctx.guild.ban(member, reason="不適切な発言")
    banned_users.add(member.id)
    await ctx.send(f"✅ {member.name} をBANしました")

# ========== LINE Bot ==========
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    reply = None  # 何も返さないときはNone

    # ===== 管理者コマンド（@トガヒミコ ～ のときだけ反応）=====
    if text.startswith("@トガヒミコ") or text.startswith("トガヒミコ"):
        cmd = text.replace("@トガヒミコ", "").replace("トガヒミコ", "").strip()

        if user_id == ADMIN_USER_ID:
            if cmd.startswith("BAN "):
                target = cmd[4:].strip()
                banned_users.add(target)
                reply = f"✅ {target} をBANリストに追加しました"
            elif cmd.startswith("解除 "):
                target = cmd[3:].strip()
                if target in banned_users:
                    banned_users.remove(target)
                    reply = f"✅ {target} のBANを解除しました"
                else:
                    reply = f"⚠️ {target} はBANされていません"
            elif cmd == "BAN一覧":
                reply = "🚫 BAN一覧:\n" + ("\n".join(banned_users) if banned_users else "なし")
            elif cmd == "ヘルプ" or cmd == "コマンド":
                reply = """📋 コマンド一覧
BAN 名前 → BAN追加
解除 名前 → BAN解除
BAN一覧 → 一覧表示
ヘルプ → この画面"""
        else:
            reply = "⚠️ 管理者のみコマンドが使えます"

    # ===== NGワード検知（指定された3つだけ）=====
    NG_WORDS = ["馬鹿", "死ね", "殺す"]
    if any(word in text for word in NG_WORDS):
        reply = "⚠️ 不適切な発言を検知しました。\nグループのルールを守ってください。\n繰り返すとBANされる場合があります。"

    # ===== 返事があるときだけ送信 =====
    if reply:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )

# ========== 起動 ==========
if __name__ == "__main__":
    import threading
    if DISCORD_BOT_TOKEN:
        threading.Thread(
            target=lambda: discord_bot.run(DISCORD_BOT_TOKEN),
            daemon=True
        ).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
