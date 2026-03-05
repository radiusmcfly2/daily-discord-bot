import os
import datetime
import discord
from discord.ext import commands, tasks

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

START_DATE = datetime.date(2026, 3, 5)

def load_lines(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

prompts = load_lines("prompts.txt")
songs = load_lines("music.txt")
words = load_lines("words.txt")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

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

async def send_daily_message(channel):
    today = datetime.date.today()
    day_index = (today - START_DATE).days

    if day_index < 0:
        print("Startdatum noch nicht erreicht")
        return

    message = build_message(day_index)
    await channel.send(message)

@bot.event
async def on_ready():
    print(f"Bot ist online: {bot.user}")

    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)

    print("Slash Commands synchronisiert")

@bot.tree.command(name="preview", description="Zeigt die heutige Daily Nachricht", guild=discord.Object(id=GUILD_ID))
async def preview(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    guild = bot.get_guild(GUILD_ID)

    if guild is None:
        await interaction.followup.send("Server nicht gefunden.", ephemeral=True)
        return

    channel = discord.utils.get(guild.text_channels, name="daily")

    if channel is None:
        await interaction.followup.send("Channel #daily nicht gefunden.", ephemeral=True)
        return

    await send_daily_message(channel)

    await interaction.followup.send("Preview gesendet.", ephemeral=True)

@tasks.loop(minutes=5)
async def daily_post():
    now = datetime.datetime.utcnow()

    if now.hour != 19:
        return

    guild = bot.get_guild(GUILD_ID)

    if guild is None:
        return

    channel = discord.utils.get(guild.text_channels, name="daily")

    if channel is None:
        return

    await send_daily_message(channel)

bot.run(TOKEN)
