from __future__ import annotations

import asyncio

import discord
from deep_translator import GoogleTranslator
from discord.ext import commands

from settings_store import get_guild_settings


class TranslateCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.translator = GoogleTranslator(source="en", target="de")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return

        settings = await get_guild_settings(message.guild.id)
        if not settings["translation_enabled"]:
            return

        text = message.content.strip()
        if not text or text.startswith(("!", "/", "http://", "https://")):
            return

        try:
            translated = await asyncio.to_thread(
                self.translator.translate,
                text,
            )
        except Exception as error:
            print(f"[Übersetzung] {error}")
            return

        if translated and translated.casefold() != text.casefold():
            await message.reply(
                f"🇩🇪 **Übersetzung:**\n{translated}",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TranslateCog(bot))
