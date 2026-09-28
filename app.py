import discord
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Bot起動: {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content.strip() == "!ID一覧":
        text = "【メンバーID一覧】\n"
        for member in message.guild.members:
            text += f"・{member.display_name} ／ `{member.id}`\n"
        await message.channel.send(text)

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
client.run(TOKEN)
