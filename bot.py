import discord
from discord.ext import commands
import os
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("Bot ist online:", bot.user)
    for channel in bot.get_all_channels():
        if channel.name == "daily":
            await channel.send(
                "✅ **Testnachricht**\n"
                "Prompt: Zeichne etwas Unfertiges.\n"
                "Frage: Was war heute unnötig?\n"
                "Song: Pink Floyd – Time"
            )

bot.run(TOKEN)
