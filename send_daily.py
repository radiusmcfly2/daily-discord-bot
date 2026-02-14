# send_daily.py
import os
import sys
import datetime
import json
import requests

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
START_ISO = os.getenv("START_DATETIME_UTC", "2026-03-04T19:00:00Z")

if not WEBHOOK:
    print("ERROR: DISCORD_WEBHOOK_URL not set")
    sys.exit(1)

def load_lines(fn):
    with open(fn, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]

prompts = load_lines("prompts.txt")
songs = load_lines("music.txt")
words = load_lines("words.txt")

def parse_iso_z(s):
    if s.endswith("Z"):
        s = s[:-1]
    # return aware UTC datetime
    return datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc)

START_DT = parse_iso_z(START_ISO)
now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

# don't post before start
if now_utc < START_DT:
    print("Not started yet. Start at", START_DT.isoformat())
    sys.exit(0)

# compute day index (days since start date, anchored to UTC date boundaries)
today_midnight_utc = datetime.datetime.combine(now_utc.date(), datetime.time(0,0), tzinfo=datetime.timezone.utc)
start_midnight_utc = datetime.datetime.combine(START_DT.date(), datetime.time(0,0), tzinfo=datetime.timezone.utc)
day_index = int((today_midnight_utc - start_midnight_utc).total_seconds() // 86400)
if day_index < 0:
    print("day_index negative, exiting")
    sys.exit(0)

prompt = prompts[day_index % len(prompts)]
song = songs[day_index % len(songs)]
word = words[day_index % len(words)]

content = (
    f"📅 **Daily Kalender**\n\n"
    f"🎨 **Prompt**\n{prompt}\n\n"
    f"🧠 **Word of the Day**\n{word}\n\n"
    f"🎵 **Song**\n{song}"
)

payload = {"content": content}

r = requests.post(WEBHOOK, json=payload)
print("Webhook POST status:", r.status_code, r.text)
if r.status_code >= 400:
    sys.exit(2)

print("Posted successfully for day_index", day_index)
