from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import re

app = Flask(__name__)

# 環境変数から取得
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ===== 自分のLINE IDに書き換えて！ =====
ADMIN_USER_ID = "Ubb14dba8c75028d85c7ada12a3f4177c"
# ======================================

# 管理者用：荒らし対象者を記録
banned_users = set()

# ---------- Discord Bot 部分 ----------
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

discord_bot = commands.Bot(command_prefix="!", intents=intents)

@discord_bot.event
async def on_ready():
    print(f"Discord Bot ログイン完了: {discord_bot.user}")

@discord_bot.command(name="メンバー", help="サーバーメンバー一覧を表示")
async def list_members(ctx):
    members = [m.name for m in ctx.guild.members if not m.bot]
    await ctx.send(f"👥 メンバー数: {len(members)}人\n" + "\n".join(members[:30]))

@discord_bot.command(name="BAN", help="メンバーをBAN !BAN @名前")
async def ban_member(ctx, member: discord.Member = None):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 管理者権限が必要です")
        return
    if not member:
        await ctx.send("❌ 対象を指定してください: !BAN @ユーザー名")
        return
    await ctx.guild.ban(member, reason="荒らし防止")
    banned_users.add(member.id)
    await ctx.send(f"✅ {member.name} をBANしました")

# ---------- LINE Bot 部分 ----------
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

    # 管理者コマンド
    if user_id == ADMIN_USER_ID:
        if text.startswith("BAN "):
            target = text[4:].strip()
            reply = f"✅ {target} をBANリストに追加しました"
        elif text == "メンバー一覧":
            reply = "👥 Discord側で !メンバー と打って確認してください"
        else:
            reply = f"受信: {text}\nコマンド：\n・BAN 名前\n・メンバー一覧"
    else:
        # 荒らしっぽいワード検知
        ban_words = ["荒らし", "宣伝", "スパム"]
        if any(w in text for w in ban_words):
            reply = "⚠️ 不適切な単語を検知しました。発言を控えてください。"
        else:
            reply = f"トガヒミコ「{text}」って言ったね！"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# ---------- 起動 ----------
if __name__ == "__main__":
    import threading
    # Discord Botを別スレッドで起動
    if DISCORD_BOT_TOKEN:
        threading.Thread(
            target=lambda: discord_bot.run(DISCORD_BOT_TOKEN),
            daemon=True
        ).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
