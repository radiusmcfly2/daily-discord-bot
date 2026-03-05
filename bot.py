import os
import datetime
import discord
from discord.ext import commands, tasks

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

CHANNEL_NAME = "daily"
START_DATE = datetime.date(2026, 3, 5)
POST_HOUR_UTC = 19

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


def build_message(day_index):
    prompt = prompts[day_index % len(prompts)]
    song = songs[day_index % len(songs)]
    word = words[day_index % len(words)]

    return (
        f"📅 **Daily Kalender**\n\n"
        f"🎨 **Prompt**\n{prompt}\n\n"
        f"🧠 **Word of the Day**\n{word}\n\n"
        f"🎵 **Song**\n{song}"
    )


def get_day_index(date):
    return (date - START_DATE).days


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


async def send_daily(channel, date=None):
    if date is None:
        date = datetime.date.today()

    day_index = get_day_index(date)

    if day_index < 0:
        print("Startdatum noch nicht erreicht.")
        return

    message = build_message(day_index)

    await channel.send(message)

    set_last_post_date(date.isoformat())

    print(f"Posted day {day_index}")


@bot.event
async def on_ready():
    print(f"Bot ist online: {bot.user}")

    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)

    print("Slash commands synchronisiert.")

    if not daily_post.is_running():
        daily_post.start()


@bot.tree.command(
    name="preview",
    description="Zeigt die heutige Nachricht",
    guild=discord.Object(id=GUILD_ID)
)
async def preview(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    guild = bot.get_guild(GUILD_ID)

    if guild is None:
        await interaction.followup.send("Server nicht gefunden.", ephemeral=True)
        return

    channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)

    if channel is None:
        await interaction.followup.send("Channel nicht gefunden.", ephemeral=True)
        return

    today = datetime.date.today()

    await send_daily(channel, today)

    await interaction.followup.send("Preview gesendet.", ephemeral=True)


@tasks.loop(minutes=5)
async def daily_post():
    now = datetime.datetime.utcnow()

    if now.hour != POST_HOUR_UTC:
        return

    today = datetime.date.today()

    if get_last_post_date() == today.isoformat():
        return

    guild = bot.get_guild(GUILD_ID)

    if guild is None:
        print("Guild nicht gefunden.")
        return

    channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)

    if channel is None:
        print("Channel nicht gefunden.")
        return

    await send_daily(channel, today)


bot.run(TOKEN)
