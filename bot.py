import os
import json
import time
import datetime
import discord
from discord.ext import commands, tasks

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
OWNER_ID = int(os.getenv("OWNER_ID")) if os.getenv("OWNER_ID") else None

START_DATETIME_UTC = os.getenv("START_DATETIME_UTC", "2026-03-04T19:00:00Z")
POST_HOUR_UTC = int(os.getenv("POST_HOUR_UTC")) if os.getenv("POST_HOUR_UTC") else 19

LAST_POST_INDEX_FILE = "last_post_index.txt"
LOGIN_STATE_FILE = "login_state.json"

INITIAL_BACKOFF = 60 * 5
MAX_BACKOFF = 60 * 60 * 24

def load_lines(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

prompts = load_lines("prompts.txt")
songs = load_lines("music.txt")
words = load_lines("words.txt")

def get_last_post_index():
    if not os.path.exists(LAST_POST_INDEX_FILE):
        return None
    try:
        with open(LAST_POST_INDEX_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None

def set_last_post_index(idx):
    with open(LAST_POST_INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(str(int(idx)))

def parse_start_datetime(iso_str):
    # akzeptiert Formate wie "2026-03-04T19:00:00Z" oder "2026-03-04T19:00:00"
    if iso_str.endswith("Z"):
        iso_str = iso_str[:-1]
    return datetime.datetime.fromisoformat(iso_str).replace(tzinfo=datetime.timezone.utc)

START_DT_UTC = parse_start_datetime(START_DATETIME_UTC)

def load_login_state():
    if not os.path.exists(LOGIN_STATE_FILE):
        return {"next_allowed": None, "backoff": INITIAL_BACKOFF}
    try:
        with open(LOGIN_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"next_allowed": None, "backoff": INITIAL_BACKOFF}

def save_login_state(state):
    with open(LOGIN_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

def sleep_seconds(s):
    remaining = int(s)
    while remaining > 0:
        step = min(60, remaining)
        print(f"[sleep] {remaining} sec remaining...")
        time.sleep(step)
        remaining -= step

def create_bot():
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    async def send_compiled_message_to_channel(channel, target_date=None):
        if target_date is None:
            now_date = (datetime.datetime.utcnow()).date()
        else:
            now_date = target_date
     
        delta_days = int((datetime.datetime.combine(now_date, datetime.time(0,0, tzinfo=datetime.timezone.utc)) - START_DT_UTC).total_seconds() // 86400)
        day_index = delta_days
        if day_index < 0:
            return
        prompt = prompts[day_index % len(prompts)]
        song = songs[day_index % len(songs)]
        word = words[day_index % len(words)]
        content = (
            f"🎨 **Prompt of the Day**\n{prompt}\n\n"
            f"🧠 **Word of the Day**\n{word}\n\n"
            f"🎵 **Song of the Day**\n{song}"
        )
        await channel.send(content)

    @bot.event
    async def on_ready():
        print("Bot ist online:", bot.user)
        if GUILD_ID:
            try:
                await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
                print(f"[info] Tree commands synced for guild {GUILD_ID}")
            except Exception as e:
                print("[warn] Sync-Fehler:", e)
        daily_post.start()

    if GUILD_ID:
        @bot.tree.command(name="preview", description="Sende die heutige Daily-Nachricht (nur Owner).", guild=discord.Object(id=GUILD_ID))
        async def preview(interaction: discord.Interaction):
            if OWNER_ID and interaction.user.id != OWNER_ID:
                await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
                return
            await interaction.response.defer(thinking=True, ephemeral=True)
            guild = bot.get_guild(GUILD_ID)
            if not guild:
                await interaction.followup.send("Fehler: Bot ist nicht in der erwarteten Guild.", ephemeral=True)
                return
            channel = discord.utils.get(guild.text_channels, name="daily")
            if not channel:
                await interaction.followup.send("Kanal #daily nicht gefunden.", ephemeral=True)
                return
            try:
                # preview uses today's date in friend's local sense (handled by send_compiled_message)
                await send_compiled_message_to_channel(channel)
                await interaction.followup.send("ALLES GUT DU HURENSOHN.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Fehler beim Senden: {e}", ephemeral=True)
    else:
        print("[warn] GUILD_ID nicht gesetzt — kein /preview-Command registriert.")

    @tasks.loop(minutes=5)
    async def daily_post():
        now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        # If now is before start datetime, do nothing
        if now_utc < START_DT_UTC:
            return

        # compute current day_index using start anchor
        # use UTC date anchored at 00:00 and compare to start_datetime
        today_utc_midnight = datetime.datetime.combine(now_utc.date(), datetime.time(0,0, tzinfo=datetime.timezone.utc))
        day_index = int((today_utc_midnight - START_DT_UTC).total_seconds() // 86400)
        if day_index < 0:
            return

        # only post at or after configured hour (UTC)
        if now_utc.hour < POST_HOUR_UTC:
            return

        last_idx = get_last_post_index()
        if last_idx is not None and last_idx >= day_index:
            # already posted for this day_index
            return

        # find channel
        channel = None
        if GUILD_ID:
            guild = bot.get_guild(GUILD_ID)
            if not guild:
                print("[warn] Guild nicht gefunden; retry später.")
                return
            channel = discord.utils.get(guild.text_channels, name="daily")
        else:
            channel = discord.utils.get(bot.get_all_channels(), name="daily")
        if not channel:
            print("[warn] Kanal #daily nicht gefunden; retry später.")
            return

        # build and send
        prompt = prompts[day_index % len(prompts)]
        song = songs[day_index % len(songs)]
        word = words[day_index % len(words)]
        try:
            await channel.send(
                f"🎨 **Prompt of the Day**\n{prompt}\n\n"
                f"🧠 **Word of the Day**\n{word}\n\n"
                f"🎵 **Song of the Day**\n{song}"
            )
            set_last_post_index(day_index)
        except Exception as e:
            print("[error] Fehler beim Senden:", e)

    return bot

def main_loop():
    state = load_login_state()
    backoff = state.get("backoff", INITIAL_BACKOFF)
    next_allowed = None
    if state.get("next_allowed"):
        try:
            next_allowed = datetime.datetime.fromisoformat(state["next_allowed"])
        except Exception:
            next_allowed = None

    while True:
        now = datetime.datetime.utcnow()
        if next_allowed and now < next_allowed:
            wait = (next_allowed - now).total_seconds()
            print(f"[info] login blocked until {next_allowed.isoformat()} UTC — sleeping {int(wait)}s")
            sleep_seconds(wait)
            state = load_login_state()
            backoff = state.get("backoff", INITIAL_BACKOFF)
            next_allowed = None
            if state.get("next_allowed"):
                try:
                    next_allowed = datetime.datetime.fromisoformat(state["next_allowed"])
                except Exception:
                    next_allowed = None
            continue

        print("[info] creating bot and attempting to run (login attempt at UTC)", datetime.datetime.utcnow().isoformat())
        bot = create_bot()
        try:
            bot.run(TOKEN)
            print("[info] bot.run ended normally")
            return
        except Exception as e:
            msg = str(e)
            print("[error] Exception during bot.run:", msg)
            if "429" in msg or "Too Many Requests" in msg or "rate" in msg.lower():
                backoff = min(backoff * 2 if backoff else INITIAL_BACKOFF, MAX_BACKOFF)
                blocked_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=backoff)
                state = {"next_allowed": blocked_until.isoformat(), "backoff": backoff}
                save_login_state(state)
                next_allowed = blocked_until
                print(f"[warn] detected rate-limit. backing off for {backoff}s until {blocked_until.isoformat()}")
                sleep_seconds(backoff)
                continue
            if "401" in msg or "Unauthorized" in msg or "Improper token" in msg:
                print("[fatal] Token problem detected (401/Unauthorized). Please reset token in Developer Portal and update DISCORD_TOKEN.")
                backoff = MAX_BACKOFF
                blocked_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=backoff)
                state = {"next_allowed": blocked_until.isoformat(), "backoff": backoff}
                save_login_state(state)
                next_allowed = blocked_until
                sleep_seconds(backoff)
                continue
            print("[error] unexpected error, sleeping 60s before retry")
            sleep_seconds(60)
            continue

if __name__ == "__main__":
    main_loop()


