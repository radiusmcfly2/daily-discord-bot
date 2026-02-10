import discord
from discord.ext import commands, tasks
import datetime
import os

TOKEN = os.getenv("DISCORD_TOKEN")

START_DATE = datetime.date(2026, 2, 10)  # ← HIER Startdatum anpassen

def load_lines(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

prompts = load_lines("prompts.txt")
songs = load_lines("music.txt")
words = load_lines("words.txt")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("Bot ist online:", bot.user)

    today = datetime.date.today()
    day_index = (today - START_DATE).days

    prompt = prompts[day_index % len(prompts)]
    song = songs[day_index % len(songs)]
    word = words[day_index % len(words)]

    for channel in bot.get_all_channels():
        if channel.name == "daily":
            await channel.send(
                f"🧪 **TEST – Daily Kalender**\n\n"
                f"🎨 **Prompt**\n{prompt}\n\n"
                f"🧠 **Word of the Day**\n{word}\n\n"
                f"🎵 **Song of the Day**\n{song}"
            )

    daily_post.start()


@tasks.loop(minutes=1)
async def daily_post():
    now = datetime.datetime.now()

    if now.hour == 17 and now.minute == 27:  # Uhrzeit
        today = datetime.date.today()
        day_index = (today - START_DATE).days

        prompt = prompts[day_index % len(prompts)]
        song = songs[day_index % len(songs)]
        word = words[day_index % len(words)]

        for channel in bot.get_all_channels():
            if channel.name == "daily":
                await channel.send(
                    f"📅 **Daily Kalender**\n\n"
                    f"🎨 **Prompt**\n{prompt}\n\n"
                    f"🧠 **Word of the Day**\n{word}\n\n"
                    f"🎵 **Song of the Day**\n{song}"
                )

bot.run(TOKEN)
