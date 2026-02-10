import discord
from discord.ext import commands, tasks
import datetime
import os

TOKEN = os.getenv("DISCORD_TOKEN")

START_DATE = datetime.date(2026, 2, 10)
POST_HOUR_UTC = 8  # 08:00 UTC ≈ 09:00 MEZ

LAST_POST_FILE = "last_post.txt"

def load_lines(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

prompts = load_lines("prompts.txt")
songs = load_lines("music.txt")
words = load_lines("words.txt")

def get_last_post_date():
    if not os.path.exists(LAST_POST_FILE):
        return None
    with open(LAST_POST_FILE, "r") as f:
        return f.read().strip()

def set_last_post_date(date_str):
    with open(LAST_POST_FILE, "w") as f:
        f.write(date_str)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("Bot ist online:", bot.user)
    daily_post.start()

@tasks.loop(minutes=5)
async def daily_post():
    now = datetime.datetime.utcnow()
    today_str = now.date().isoformat()

    # Schon heute gepostet?
    if get_last_post_date() == today_str:
        return

    # Noch nicht die Uhrzeit?
    if now.hour < POST_HOUR_UTC:
        return

    day_index = (now.date() - START_DATE).days

    prompt = prompts[day_index % len(prompts)]
    song = songs[day_index % len(songs)]
    word = words[day_index % len(words)]

    for channel in bot.get_all_channels():
        if channel.name == "daily":
            await channel.send(
                f"📅 **Daily Kalender**\n\n"
                f"🎨 **Prompt**\n{prompt}\n\n"
                f"🧠 **Word of the Day**\n{word}\n\n"
                f"🎵 **Song**\n{song}"
            )

    set_last_post_date(today_str)

bot.run(TOKEN)
