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

# 起動時
@client.event
async def on_ready():
    print(f"✅ Bot起動: {client.user}")

# メッセージ処理
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.strip() == "!ID一覧":
        text = "【メンバーID一覧】\n"
        for member in message.guild.members:
            text += f"・{member.display_name} ／ `{member.id}`\n"
        await message.channel.send(text)

# 起動
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
client.run(TOKEN)
