from __future__ import annotations

import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs.verify import VerifyView


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN fehlt. Kopiere .env.example zu .env "
        "und trage dort deinen neuen Token ein."
    )

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

EXTENSIONS = (
    "cogs.setup",
    "cogs.verify",
    "cogs.translate",
    "cogs.welcome",
    "cogs.birthdays",
    "cogs.moderation",
    "cogs.morning",
)


@bot.event
async def setup_hook() -> None:
    # Bereits gesendete Verifizierungsbuttons funktionieren auch nach Neustarts.
    bot.add_view(VerifyView())

    for extension in EXTENSIONS:
        await bot.load_extension(extension)
        print(f"[OK] {extension} geladen")

    synced = await bot.tree.sync()
    print(f"[OK] {len(synced)} Slash-Befehl(e) synchronisiert")


@bot.event
async def on_ready() -> None:
    print(f"{bot.user} ist online!")
    await bot.change_presence(activity=discord.Game(name="/setup status"))


bot.run(TOKEN)
