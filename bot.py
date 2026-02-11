# bot.py — robust gegen 429 Rate-Limits, persistenter Backoff
import discord
from discord.ext import commands, tasks
import datetime
import os
import time
import json

TOKEN = os.getenv("DISCORD_TOKEN")

# Konfiguration
START_DATE = datetime.date(2026, 2, 10)
POST_HOUR_UTC = 8  # 08:00 UTC (~09:00 MEZ)
LAST_POST_FILE = "last_post.txt"
LOGIN_STATE_FILE = "login_state.json"

# Backoff-Parameter (in Sekunden)
INITIAL_BACKOFF = 60 * 5        # 5 Minuten erste Wartezeit nach Problem
MAX_BACKOFF = 60 * 60 * 24      # max 24 Stunden

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
    with open(LAST_POST_FILE, "w", encoding="utf-8") as f:
        f.write(date_str)

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
    # sleep in small increments so Railway logs etwas zeigt
    remaining = int(s)
    while remaining > 0:
        step = min(60, remaining)
        print(f"[sleep] {remaining} sec remaining...")
        time.sleep(step)
        remaining -= step

def create_bot():
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

        # Uhrzeit-Check: erst posten, wenn Stunde erreicht
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
            # reload state after sleeping (in case someone edited)
            state = load_login_state()
            backoff = state.get("backoff", INITIAL_BACKOFF)
            next_allowed = None
            if state.get("next_allowed"):
                try:
                    next_allowed = datetime.datetime.fromisoformat(state["next_allowed"])
                except Exception:
                    next_allowed = None
            continue

        # Versuch, Bot zu starten
        print("[info] creating bot and attempting to run (login attempt at UTC)", datetime.datetime.utcnow().isoformat())
        bot = create_bot()
        try:
            # Blockiert bis Bot beendet/exception
            bot.run(TOKEN)
            # wenn bot.run jemals sauber zurückkommt, brechen wir die Schleife
            print("[info] bot.run ended normally")
            return
        except Exception as e:
            msg = str(e)
            print("[error] Exception during bot.run:", msg)

            # Wenn es eindeutig ein Rate-Limit (429) ist
            if "429" in msg or "Too Many Requests" in msg or "rate" in msg.lower():
                # Erhöhe Backoff (exponentiell), aber begrenze
                backoff = min(backoff * 2 if backoff else INITIAL_BACKOFF, MAX_BACKOFF)
                blocked_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=backoff)
                state = {"next_allowed": blocked_until.isoformat(), "backoff": backoff}
                save_login_state(state)
                next_allowed = blocked_until
                print(f"[warn] detected rate-limit. backing off for {backoff}s until {blocked_until.isoformat()}")
                sleep_seconds(backoff)
                continue

            # Token/Authentifizierungsfehler: 401/Unauthorized
            if "401" in msg or "Unauthorized" in msg or "Improper token" in msg:
                print("[fatal] Token problem detected (401/Unauthorized). Please reset token in Developer Portal and update DISCORD_TOKEN.")
                # Wir setzen einen längeren Backoff, damit nicht in Endlosschleife
                backoff = MAX_BACKOFF
                blocked_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=backoff)
                state = {"next_allowed": blocked_until.isoformat(), "backoff": backoff}
                save_login_state(state)
                next_allowed = blocked_until
                sleep_seconds(backoff)
                continue

            # Andere Fehler: kurze Pause und nochmal versuchen
            print("[error] unexpected error, sleeping 60s before retry")
            sleep_seconds(60)
            continue

if __name__ == "__main__":
    main_loop()
