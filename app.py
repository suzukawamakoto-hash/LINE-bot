import discord
from discord.ext import commands
import os

# インテント設定
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

# Botの準備
client = discord.Client(intents=intents)

# 起動時のメッセージ
@client.event
async def on_ready():
    print(f"Botが起動しました！ → {client.user}")
    print("------")

# メッセージを受け取ったとき
@client.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == client.user:
        return

    # !ID一覧 コマンド
    if message.content.strip() == "!ID一覧":
        text = "【メンバーID一覧】\n"
        for member in message.guild.members:
            text += f"・{member.display_name} ／ `{member.id}`\n"
        await message.channel.send(text)
        return

# トークンで起動
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
client.run(TOKEN)
