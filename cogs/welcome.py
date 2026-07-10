from __future__ import annotations

import discord
from discord.ext import commands

from settings_store import get_guild_settings


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def get_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        settings = await get_guild_settings(guild.id)
        channel_id = settings["welcome_channel_id"]
        channel = guild.get_channel(channel_id) if channel_id else None
        return channel if isinstance(channel, discord.TextChannel) else None

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        channel = await self.get_channel(member.guild)
        if channel is None:
            return

        embed = discord.Embed(
            title="🔮 Willkommen!",
            description=(
                f"Herzlich willkommen, {member.mention}!\n\n"
                "Bitte verifiziere dich, um Zugriff auf den Server zu erhalten."
            ),
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="👥 Mitglieder",
            value=f"Du bist Mitglied Nummer **{member.guild.member_count}**.",
            inline=False,
        )
        embed.set_footer(text="Grimo • Welcome")

        try:
            await channel.send(content=member.mention, embed=embed)
        except discord.Forbidden:
            print(f"[Welcome] Keine Senderechte in #{channel.name}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        channel = await self.get_channel(member.guild)
        if channel is None:
            return

        embed = discord.Embed(
            title="👋 Mitglied hat den Server verlassen",
            description=(
                f"**{member.display_name}** hat den Server verlassen.\n\n"
                f"🆔 ID: `{member.id}`\n"
                f"👥 Verbleibende Mitglieder: **{member.guild.member_count}**"
            ),
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Grimo • Goodbye")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"[Goodbye] Keine Senderechte in #{channel.name}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
