# — Wichtig: dieser Code ersetzt die create_bot()-Funktion und den Teil, der das Bot-Objekt erzeugt.
#           Er setzt voraus, dass prompts, songs, words, START_DATE, POST_HOUR_UTC, TOKEN usw. bereits definiert sind.

GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
OWNER_ID = int(os.getenv("OWNER_ID")) if os.getenv("OWNER_ID") else None

def create_bot():
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    async def send_compiled_message_to_channel(channel):
        """Hilfsfunktion: Baut die heutige Nachricht und sendet sie in channel."""
        now = datetime.datetime.utcnow().date()
        day_index = (now - START_DATE).days
        prompt = prompts[day_index % len(prompts)]
        song = songs[day_index % len(songs)]
        word = words[day_index % len(words)]

        content = (
            f"📅 **Daily Kalender**\n\n"
            f"🎨 **Prompt**\n{prompt}\n\n"
            f"🧠 **Word of the Day**\n{word}\n\n"
            f"🎵 **Song**\n{song}"
        )
        await channel.send(content)

    @bot.event
    async def on_ready():
        print("Bot ist online:", bot.user)

        # Falls GUILD_ID gesetzt ist, syncen wir die guild-scoped commands direkt (schnell sichtbar)
        if GUILD_ID:
            try:
                await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
                print(f"[info] Tree commands synced for guild {GUILD_ID}")
            except Exception as e:
                print("[warn] Fehler beim Sync der Commands:", str(e))

        # Starte die tägliche Loop (sie prüft täglich und sendet nur einmal)
        daily_post.start()

    # --- Slash-Command zur manuellen Vorschau (nur im Test-Guild verfügbar) ---
    # /preview — nur Owner darf auslösen
    if GUILD_ID:
        @bot.tree.command(name="preview", description="Sende die heutige Daily-Nachricht (nur Owner).", guild=discord.Object(id=GUILD_ID))
        async def preview(interaction: discord.Interaction):
            # Sicherheit: nur OWNER darf den Befehl ausführen
            if OWNER_ID and interaction.user.id != OWNER_ID:
                await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True, ephemeral=True)  # sofortiges Feedback
            # finde den Kanal im Guild-Objekt
            guild = bot.get_guild(GUILD_ID)
            if not guild:
                await interaction.followup.send("Fehler: Bot ist nicht in der erwarteten Guild.", ephemeral=True)
                return

            channel = discord.utils.get(guild.text_channels, name="daily")
            if not channel:
                await interaction.followup.send("Kanal #daily nicht gefunden.", ephemeral=True)
                return

            try:
                await send_compiled_message_to_channel(channel)
                await interaction.followup.send("Testnachricht gesendet.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Fehler beim Senden: {e}", ephemeral=True)

    # Falls keine GUILD_ID gesetzt: wir registrieren keinen guild-scoped preview-command
    else:
        print("[warn] GUILD_ID nicht gesetzt — kein /preview-Command registriert.")

    # Der daily_post loop sollte bereits in deinem bestehenden Code die tägliche Logik abdecken.
    @tasks.loop(minutes=5)
    async def daily_post():
        now = datetime.datetime.utcnow()
        today_str = now.date().isoformat()

        if get_last_post_date() == today_str:
            return
        if now.hour < POST_HOUR_UTC:
            return

        # finde den Kanal im (ersten) bekannten Guild
        if GUILD_ID:
            guild = bot.get_guild(GUILD_ID)
            if not guild:
                print("[warn] Guild nicht gefunden; wartet.")
                return
            channel = discord.utils.get(guild.text_channels, name="daily")
        else:
            # Fallback: suche kanal global
            channel = discord.utils.get(bot.get_all_channels(), name="daily")

        if not channel:
            print("[warn] Kanal #daily nicht gefunden; retry später.")
            return

        # Sende Nachricht
        day_index = (now.date() - START_DATE).days
        prompt = prompts[day_index % len(prompts)]
        song = songs[day_index % len(songs)]
        word = words[day_index % len(words)]

        try:
            await channel.send(
                f"📅 **Daily Kalender**\n\n"
                f"🎨 **Prompt**\n{prompt}\n\n"
                f"🧠 **Word of the Day**\n{word}\n\n"
                f"🎵 **Song**\n{song}"
            )
            set_last_post_date(now.date().isoformat())
        except Exception as e:
            print("[error] Fehler beim Senden der täglichen Nachricht:", e)

    return bot
