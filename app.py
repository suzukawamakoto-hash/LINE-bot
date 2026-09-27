from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

# ===== 環境変数から自動取得 =====
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ===== ↓自分のLINE IDに書き換える！=====
ADMIN_USER_ID = "Ubb14dba8c75028d85c7ada12a3f4177c"
# ======================================

banned_users = set()

# ========== Discord Bot 部分 ==========
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

discord_bot = commands.Bot(command_prefix="!", intents=intents)

@discord_bot.event
async def on_ready():
    print(f"✅ Discord Bot 起動完了: {discord_bot.user}")

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
    await ctx.guild.ban(member, reason="荒らし防止")
    banned_users.add(member.id)
    await ctx.send(f"✅ {member.name} をBANしました")

@discord_bot.command(name="KICK")
async def cmd_kick(ctx, member: discord.Member = None):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 管理者権限が必要です")
        return
    if not member:
        await ctx.send("❌ 使い方: !KICK @ユーザー名")
        return
    await ctx.guild.kick(member, reason="荒らし防止")
    await ctx.send(f"✅ {member.name} をキックしました")

@discord_bot.command(name="ヘルプ")
async def cmd_help_discord(ctx):
    text = """📋 Discord コマンド一覧
!メンバー → メンバー一覧表示
!BAN @名前 → メンバーをBAN
!KICK @名前 → メンバーをキック
!ヘルプ → この一覧"""
    await ctx.send(text)

# ========== LINE Bot 部分 ==========
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
    reply = ""

    # ===== 管理者専用コマンド =====
    if user_id == ADMIN_USER_ID:
        if text.startswith("BAN "):
            target = text[4:].strip()
            banned_users.add(target)
            reply = f"✅ {target} をBANリストに追加しました"

        elif text.startswith("解除 "):
            target = text[3:].strip()
            if target in banned_users:
                banned_users.remove(target)
                reply = f"✅ {target} のBANを解除しました"
            else:
                reply = f"⚠️ {target} はBANされていません"

        elif text == "BAN一覧":
            if banned_users:
                reply = "🚫 BAN 一覧:\n" + "\n".join(banned_users)
            else:
                reply = "✅ BANされている人はいません"

        elif text == "メンバー一覧":
            reply = "👥 Discordで「!メンバー」と送信して確認してください"

        elif text == "ヘルプ":
            reply = """📋 LINE コマンド一覧
BAN 名前 → BANリスト追加
解除 名前 → BAN解除
BAN一覧 → BANされた人を表示
メンバー一覧 → Discordで確認
ヘルプ → この一覧"""

        else:
            reply = f"トガヒミコ「{text}」って言ったね！\n「ヘルプ」でコマンド一覧が見れるよ"

    # ===== 一般ユーザー =====
    else:
        NG_WORDS = ["荒らし", "宣伝", "スパム", "死ね", "消えろ"]
        if any(word in text for word in NG_WORDS):
            reply = "⚠️ 不適切な言葉を検知しました。\n繰り返すとBANされる場合があります。"
        else:
            reply = f"トガヒミコ「{text}」って言ったね！"

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
