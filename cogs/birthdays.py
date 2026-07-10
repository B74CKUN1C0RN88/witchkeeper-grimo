from __future__ import annotations

import asyncio
import calendar
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from settings_store import get_guild_settings

BIRTHDAYS_FILE = Path(__file__).resolve().parent.parent / "data" / "birthdays.json"
BERLIN = ZoneInfo("Europe/Berlin")
_LOCK = asyncio.Lock()


def _read_data() -> dict:
    BIRTHDAYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not BIRTHDAYS_FILE.exists():
        BIRTHDAYS_FILE.write_text("{}", encoding="utf-8")
    try:
        data = json.loads(BIRTHDAYS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_data(data: dict) -> None:
    temporary = BIRTHDAYS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(BIRTHDAYS_FILE)


def _guild_data(data: dict, guild_id: int) -> dict:
    current = data.setdefault(str(guild_id), {})
    if "birthdays" not in current:
        old_entries = {key: value for key, value in current.items() if str(key).isdigit() and isinstance(value, dict)}
        current = {"birthdays": old_entries, "last_announcements": {}}
        data[str(guild_id)] = current
    current.setdefault("last_announcements", {})
    return current


class BirthdayCog(commands.GroupCog, group_name="birthday", group_description="Verwaltet Geburtstage."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()
        self.birthday_worker.start()

    def cog_unload(self) -> None:
        self.birthday_worker.cancel()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message("Dieser Befehl funktioniert nur auf einem Server.", ephemeral=True)
            return False
        return True

    @app_commands.command(name="set", description="Speichert deinen Geburtstag.")
    @app_commands.describe(tag="Tag", monat="Monat", jahr="Geburtsjahr (optional)")
    async def set_birthday(self, interaction: discord.Interaction, tag: app_commands.Range[int, 1, 31], monat: app_commands.Range[int, 1, 12], jahr: app_commands.Range[int, 1900, 2100] | None = None) -> None:
        if tag > calendar.monthrange(jahr or 2000, monat)[1]:
            await interaction.response.send_message("Dieses Datum existiert nicht.", ephemeral=True)
            return
        async with _LOCK:
            data = _read_data()
            _guild_data(data, interaction.guild_id)["birthdays"][str(interaction.user.id)] = {"day": tag, "month": monat, "year": jahr}
            _write_data(data)
        year_text = str(jahr) if jahr else "Jahr verborgen"
        await interaction.response.send_message(f"🎂 Dein Geburtstag wurde als **{tag:02d}.{monat:02d}.** gespeichert ({year_text}).", ephemeral=True)

    @app_commands.command(name="remove", description="Löscht deinen gespeicherten Geburtstag.")
    async def remove_birthday(self, interaction: discord.Interaction) -> None:
        async with _LOCK:
            data = _read_data()
            removed = _guild_data(data, interaction.guild_id)["birthdays"].pop(str(interaction.user.id), None)
            _write_data(data)
        message = "🗑️ Dein Geburtstag wurde gelöscht." if removed else "Du hast keinen Geburtstag gespeichert."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="show", description="Zeigt einen gespeicherten Geburtstag.")
    @app_commands.describe(mitglied="Optional: ein anderes Mitglied")
    async def show_birthday(self, interaction: discord.Interaction, mitglied: discord.Member | None = None) -> None:
        member = mitglied or interaction.user
        async with _LOCK:
            entry = _guild_data(_read_data(), interaction.guild_id)["birthdays"].get(str(member.id))
        if not entry:
            await interaction.response.send_message(f"Für {member.mention} ist kein Geburtstag gespeichert.", ephemeral=True)
            return
        date_text = f"{entry['day']:02d}.{entry['month']:02d}."
        if entry.get("year"):
            date_text += str(entry["year"])
        await interaction.response.send_message(f"🎂 {member.mention}: **{date_text}**")

    @app_commands.command(name="list", description="Zeigt die nächsten Geburtstage auf diesem Server.")
    async def list_birthdays(self, interaction: discord.Interaction) -> None:
        async with _LOCK:
            entries = dict(_guild_data(_read_data(), interaction.guild_id)["birthdays"])
        today = datetime.now(BERLIN).date()
        upcoming = []
        for user_id, entry in entries.items():
            member = interaction.guild.get_member(int(user_id))
            if member is None:
                continue
            try:
                next_date = today.replace(month=entry["month"], day=entry["day"])
            except ValueError:
                next_date = today.replace(month=2, day=28)
            if next_date < today:
                try:
                    next_date = next_date.replace(year=today.year + 1)
                except ValueError:
                    next_date = next_date.replace(year=today.year + 1, day=28)
            upcoming.append((next_date, member, entry))
        upcoming.sort(key=lambda item: item[0])
        if not upcoming:
            await interaction.response.send_message("Auf diesem Server sind noch keine Geburtstage gespeichert.", ephemeral=True)
            return
        lines = [f"**{entry['day']:02d}.{entry['month']:02d}.** – {member.mention}" for _, member, entry in upcoming[:20]]
        embed = discord.Embed(title="🎂 Nächste Geburtstage", description="\n".join(lines), color=discord.Color.purple())
        await interaction.response.send_message(embed=embed)

    @tasks.loop(minutes=30)
    async def birthday_worker(self) -> None:
        now = datetime.now(BERLIN)
        today_key = now.date().isoformat()
        async with _LOCK:
            data = _read_data()
            changed = False
            for guild in self.bot.guilds:
                current = _guild_data(data, guild.id)
                settings = await get_guild_settings(guild.id)
                role = guild.get_role(settings.get("birthday_role_id"))
                channel = guild.get_channel(settings.get("birthday_channel_id"))
                for user_id, entry in current["birthdays"].items():
                    member = guild.get_member(int(user_id))
                    if member is None:
                        continue
                    is_birthday = entry.get("day") == now.day and entry.get("month") == now.month
                    if role:
                        try:
                            if is_birthday and role not in member.roles:
                                await member.add_roles(role, reason="Geburtstag")
                            elif not is_birthday and role in member.roles:
                                await member.remove_roles(role, reason="Geburtstag beendet")
                        except discord.Forbidden:
                            pass
                    if is_birthday and isinstance(channel, discord.TextChannel) and current["last_announcements"].get(user_id) != today_key:
                        await channel.send(f"🎉 Alles Gute zum Geburtstag, {member.mention}! 🎂")
                        current["last_announcements"][user_id] = today_key
                        changed = True
            if changed:
                _write_data(data)

    @birthday_worker.before_loop
    async def before_birthday_worker(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BirthdayCog(bot))
