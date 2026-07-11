from __future__ import annotations

import os
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from settings_store import get_guild_settings, update_guild_settings


class TwitchCog(commands.GroupCog, group_name="twitch", group_description="Verwaltet Twitch-Livebenachrichtigungen."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.access_token: str | None = None
        super().__init__()
        self.twitch_worker.start()

    def cog_unload(self) -> None:
        self.twitch_worker.cancel()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message("Dieser Befehl funktioniert nur auf einem Server.", ephemeral=True)
            return False
        return True

    async def get_token(self) -> str | None:
        if not self.client_id or not self.client_secret:
            return None
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://id.twitch.tv/oauth2/token",
                params={"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"},
            ) as response:
                if response.status != 200:
                    return None
                self.access_token = (await response.json())["access_token"]
                return self.access_token

    async def api_get(self, endpoint: str, params: list[tuple[str, str]]) -> dict | None:
        token = self.access_token or await self.get_token()
        if not token:
            return None
        headers = {"Client-Id": self.client_id, "Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.twitch.tv/helix/{endpoint}", headers=headers, params=params) as response:
                if response.status == 401:
                    self.access_token = None
                    token = await self.get_token()
                    if not token:
                        return None
                    headers["Authorization"] = f"Bearer {token}"
                    async with session.get(f"https://api.twitch.tv/helix/{endpoint}", headers=headers, params=params) as retry:
                        return await retry.json() if retry.status == 200 else None
                return await response.json() if response.status == 200 else None

    @staticmethod
    def normalize_login(value: str) -> str:
        value = value.strip().lower()
        if "twitch.tv/" in value:
            value = value.split("twitch.tv/", 1)[1]
        return value.split("/", 1)[0].split("?", 1)[0].strip()

    async def lookup_user(self, login: str) -> dict | None:
        result = await self.api_get("users", [("login", login)])
        return result["data"][0] if result and result.get("data") else None

    @app_commands.command(name="hinzufügen", description="Fügt einen Twitch-Streamer zur Beobachtung hinzu.")
    @app_commands.describe(streamer="Twitch-Name oder Kanal-Link")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_streamer(self, interaction: discord.Interaction, streamer: str) -> None:
        await interaction.response.defer(ephemeral=True)
        login = self.normalize_login(streamer)
        user = await self.lookup_user(login)
        if not user:
            await interaction.followup.send("❌ Twitch-Kanal nicht gefunden oder Twitch-API nicht eingerichtet.", ephemeral=True)
            return
        settings = await get_guild_settings(interaction.guild_id)
        streamers = list(settings["twitch_streamers"])
        if user["login"].lower() in streamers:
            await interaction.followup.send("Dieser Streamer wird bereits beobachtet.", ephemeral=True)
            return
        streamers.append(user["login"].lower())
        await update_guild_settings(interaction.guild_id, twitch_streamers=streamers)
        await interaction.followup.send(f"✅ **{user['display_name']}** wurde hinzugefügt.", ephemeral=True)

    @app_commands.command(name="entfernen", description="Entfernt einen beobachteten Twitch-Streamer.")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_streamer(self, interaction: discord.Interaction, streamer: str) -> None:
        login = self.normalize_login(streamer)
        settings = await get_guild_settings(interaction.guild_id)
        streamers = list(settings["twitch_streamers"])
        if login not in streamers:
            await interaction.response.send_message("Dieser Streamer steht nicht auf der Liste.", ephemeral=True)
            return
        streamers.remove(login)
        live_states = dict(settings["twitch_live_states"])
        live_states.pop(login, None)
        await update_guild_settings(interaction.guild_id, twitch_streamers=streamers, twitch_live_states=live_states)
        await interaction.response.send_message(f"✅ **{login}** wurde entfernt.", ephemeral=True)

    @app_commands.command(name="liste", description="Zeigt alle beobachteten Twitch-Streamer.")
    async def list_streamers(self, interaction: discord.Interaction) -> None:
        settings = await get_guild_settings(interaction.guild_id)
        streamers = settings["twitch_streamers"]
        if not streamers:
            await interaction.response.send_message("Es werden noch keine Streamer beobachtet.", ephemeral=True)
            return
        lines = [f"• [{login}](https://twitch.tv/{login})" for login in streamers]
        embed = discord.Embed(title="🟣 Beobachtete Twitch-Streamer", description="\n".join(lines), color=discord.Color.purple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="status", description="Zeigt den Live- und letzten bekannten Streamstatus.")
    async def status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        settings = await get_guild_settings(interaction.guild_id)
        streamers = settings["twitch_streamers"]
        if not streamers:
            await interaction.followup.send("Es werden noch keine Streamer beobachtet.", ephemeral=True)
            return
        result = await self.api_get("streams", [("user_login", login) for login in streamers])
        live = {item["user_login"].lower(): item for item in (result or {}).get("data", [])}
        last_streams = settings["twitch_last_streams"]
        lines = []
        for login in streamers:
            if login in live:
                item = live[login]
                lines.append(f"🔴 **[{item['user_name']}](https://twitch.tv/{login})** – {item['game_name']}\n{item['title']}")
            elif login in last_streams:
                last = last_streams[login]
                lines.append(f"⚫ **[{login}](https://twitch.tv/{login})** – zuletzt erkannt: {last['title']}")
            else:
                lines.append(f"⚫ **[{login}](https://twitch.tv/{login})** – offline")
        embed = discord.Embed(title="Twitch-Status", description="\n\n".join(lines), color=discord.Color.purple())
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def check_guild(self, guild: discord.Guild) -> None:
        settings = await get_guild_settings(guild.id)
        streamers = settings["twitch_streamers"]
        channel = guild.get_channel(settings.get("twitch_channel_id"))
        if not streamers or not isinstance(channel, discord.TextChannel):
            return
        result = await self.api_get("streams", [("user_login", login) for login in streamers])
        if result is None:
            return
        live_items = {item["user_login"].lower(): item for item in result.get("data", [])}
        states = dict(settings["twitch_live_states"])
        last_streams = dict(settings["twitch_last_streams"])
        changed = False
        for login in streamers:
            item = live_items.get(login)
            was_live = bool(states.get(login))
            if item and not was_live:
                embed = discord.Embed(title=f"🔴 {item['user_name']} ist jetzt live!", description=item["title"], url=f"https://twitch.tv/{login}", color=discord.Color.purple(), timestamp=datetime.now(timezone.utc))
                embed.add_field(name="Kategorie", value=item.get("game_name") or "Keine Kategorie", inline=True)
                embed.add_field(name="Zuschauer", value=str(item.get("viewer_count", 0)), inline=True)
                thumbnail = item["thumbnail_url"].replace("{width}", "1280").replace("{height}", "720") + f"?t={int(datetime.now().timestamp())}"
                embed.set_image(url=thumbnail)
                embed.set_footer(text="Twitch Live-Benachrichtigung")
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    return
                states[login] = True
                last_streams[login] = {"title": item["title"], "game_name": item.get("game_name", ""), "started_at": item["started_at"]}
                changed = True
            elif item:
                last_streams[login] = {"title": item["title"], "game_name": item.get("game_name", ""), "started_at": item["started_at"]}
                if not was_live:
                    states[login] = True
                    changed = True
            elif was_live:
                states[login] = False
                changed = True
        if changed:
            await update_guild_settings(guild.id, twitch_live_states=states, twitch_last_streams=last_streams)

    @tasks.loop(minutes=2)
    async def twitch_worker(self) -> None:
        if not self.client_id or not self.client_secret:
            return
        for guild in self.bot.guilds:
            await self.check_guild(guild)

    @twitch_worker.before_loop
    async def before_twitch_worker(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TwitchCog(bot))
