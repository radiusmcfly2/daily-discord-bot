# send_daily.py
import os
import sys
import datetime
import argparse
import requests

def parse_iso_z(s):
    if s.endswith("Z"):
        s = s[:-1]
    return datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc)

# CLI
parser = argparse.ArgumentParser(description="Send daily Discord message (webhook).")
parser.add_argument("--preview", action="store_true", help="Force a post now (ignore start date).")
parser.add_argument("--offset", type=int, default=0, help="Day offset for preview (0=today, 1=tomorrow, -1=yesterday).")
args = parser.parse_args()

# Env / Config
WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
START_ISO = os.getenv("START_DATETIME_UTC", "2026-03-04T19:00:00Z").strip()
FORCE_ENV = os.getenv("FORCE_POST", "false").lower() in ("1", "true", "yes")
OFFSET_ENV = int(os.getenv("PREVIEW_OFFSET", "0"))

if not WEBHOOK:
    print("ERROR: DISCORD_WEBHOOK_URL not set")
    sys.exit(1)

try:
    START_DT = parse_iso_z(START_ISO)
except Exception as e:
    print("ERROR: START_DATETIME_UTC invalid:", repr(START_ISO))
    sys.exit(1)

def load_lines(fn):
    with open(fn, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]

prompts = load_lines("prompts.txt")
songs = load_lines("music.txt")
words = load_lines("words.txt")

# decide preview / force behavior
force = args.preview or FORCE_ENV
offset = args.offset if args.preview else (OFFSET_ENV)

now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

# compute day index helper (based on UTC midnights anchored to START_DT)
def compute_day_index_for_date(target_date):
    start_midnight = datetime.datetime.combine(START_DT.date(), datetime.time(0,0), tzinfo=datetime.timezone.utc)
    target_midnight = datetime.datetime.combine(target_date, datetime.time(0,0), tzinfo=datetime.timezone.utc)
    return int((target_midnight - start_midnight).total_seconds() // 86400)

if force:
    target_date = (now_utc + datetime.timedelta(days=offset)).date()
    print(f"[preview] forcing post for date {target_date.isoformat()} (offset={offset})")
else:
    # do the normal "not-yet-started" check
    if now_utc < START_DT:
        print("Not started yet. Start at", START_DT.isoformat())
        sys.exit(0)
    # determine today's day_index and only post if the cron/time decided so (this file used in Actions cron)
    target_date = now_utc.date()

# compute day_index
day_index = compute_day_index_for_date(target_date)
if day_index < 0:
    print("Day index < 0; nothing to post.")
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

# POST to webhook
payload = {"content": content}

print("Posting to webhook...") 
r = requests.post(WEBHOOK, json=payload)
print("Webhook POST status:", r.status_code)
if r.status_code >= 400:
    print("Response:", r.text)
    sys.exit(2)

print("Posted successfully for day_index", day_index)
sys.exit(0)
