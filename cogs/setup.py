from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from settings_store import get_guild_settings, update_guild_settings


class SetupCog(commands.GroupCog, group_name="setup", group_description="Richtet Grimo für diesen Server ein."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:

        if interaction.guild is None:
            await interaction.response.send_message(
                "Dieser Befehl funktioniert nur auf einem Server.",
                ephemeral=True
            )
            return False

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Mitglied konnte nicht erkannt werden.",
                ephemeral=True
            )
            return False

        # Serverbesitzer ODER Administrator dürfen Setup benutzen
        is_owner = interaction.guild.owner_id == interaction.user.id
        is_admin = interaction.user.guild_permissions.administrator

        if not is_owner and not is_admin:
            await interaction.response.send_message(
                "Nur der Serverinhaber oder Administratoren dürfen die Server-Einstellungen ändern.",
                ephemeral=True
            )
            return False

        return True

    @app_commands.command(
        name="verifizierung",
        description="Legt die Verifizierungsrolle fest."
    )
    async def verifizierung(
        self,
        interaction: discord.Interaction,
        rolle: discord.Role
    ):

        await update_guild_settings(
            interaction.guild.id,
            verify_role_id=rolle.id
        )

        await interaction.response.send_message(
            f"✅ Verifizierungsrolle gespeichert: {rolle.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="willkommen",
        description="Legt den Welcome-Kanal fest."
    )
    async def willkommen(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel
    ):

        await update_guild_settings(
            interaction.guild.id,
            welcome_channel_id=kanal.id
        )

        await interaction.response.send_message(
            f"✅ Welcome-Kanal gespeichert: {kanal.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="übersetzung",
        description="Übersetzung ein- oder ausschalten."
    )
    async def übersetzung(
        self,
        interaction: discord.Interaction,
        aktiviert: bool
    ):

        await update_guild_settings(
            interaction.guild.id,
            translation_enabled=aktiviert
        )

        status = "aktiviert" if aktiviert else "deaktiviert"

        await interaction.response.send_message(
            f"✅ Übersetzung wurde {status}.",
            ephemeral=True
        )

    @app_commands.command(
        name="geburtstag",
        description="Legt Geburtstagsrolle und Glückwunschkanal fest."
    )
    async def geburtstag(
        self,
        interaction: discord.Interaction,
        rolle: discord.Role,
        kanal: discord.TextChannel
    ):
        await update_guild_settings(
            interaction.guild.id,
            birthday_role_id=rolle.id,
            birthday_channel_id=kanal.id
        )

        await interaction.response.send_message(
            f"✅ Geburtstagsrolle {rolle.mention} und Kanal {kanal.mention} gespeichert.",
            ephemeral=True
        )

    @app_commands.command(
        name="status",
        description="Zeigt die aktuellen Einstellungen."
    )
    async def status(
        self,
        interaction: discord.Interaction
    ):

        settings = await get_guild_settings(interaction.guild.id)

        embed = discord.Embed(
            title="⚙️ WitchKeeper Einstellungen",
            color=discord.Color.purple()
        )

        role = interaction.guild.get_role(settings["verify_role_id"])
        channel = interaction.guild.get_channel(settings["welcome_channel_id"])

        embed.add_field(
            name="Verifizierungsrolle",
            value=role.mention if role else "Nicht gesetzt",
            inline=False
        )

        embed.add_field(
            name="Welcome-Kanal",
            value=channel.mention if channel else "Nicht gesetzt",
            inline=False
        )

        embed.add_field(
            name="Übersetzung",
            value="Aktiviert" if settings["translation_enabled"] else "Deaktiviert",
            inline=False
        )

        birthday_role = interaction.guild.get_role(settings["birthday_role_id"])
        birthday_channel = interaction.guild.get_channel(settings["birthday_channel_id"])
        moderation_channel = interaction.guild.get_channel(settings["moderation_log_channel_id"])

        embed.add_field(
            name="Geburtstagsrolle",
            value=birthday_role.mention if birthday_role else "Nicht gesetzt",
            inline=False
        )

        embed.add_field(
            name="Geburtstagskanal",
            value=birthday_channel.mention if birthday_channel else "Nicht gesetzt",
            inline=False
        )

        embed.add_field(
            name="Moderationsprotokoll",
            value=moderation_channel.mention if moderation_channel else "Nicht gesetzt",
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @app_commands.command(
        name="moderation",
        description="Legt den Kanal für Moderationsprotokolle fest."
    )
    async def moderation(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel
    ):
        await update_guild_settings(
            interaction.guild.id,
            moderation_log_channel_id=kanal.id
        )
        await interaction.response.send_message(
            f"✅ Moderationsprotokoll gespeichert: {kanal.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="morgen",
        description="Richtet die tägliche Morgenbegrüßung ein."
    )
    @app_commands.describe(kanal="Kanal für die Begrüßung", uhrzeit="Uhrzeit im Format HH:MM")
    async def morgen(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel,
        uhrzeit: str = "07:00"
    ):
        try:
            hour_text, minute_text = uhrzeit.split(":", 1)
            hour, minute = int(hour_text), int(minute_text)
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError
        except (ValueError, AttributeError):
            await interaction.response.send_message(
                "❌ Bitte nutze das Uhrzeitformat `HH:MM`, zum Beispiel `07:00`.",
                ephemeral=True
            )
            return
        normalized_time = f"{hour:02d}:{minute:02d}"
        await update_guild_settings(
            interaction.guild.id,
            morning_channel_id=kanal.id,
            morning_time=normalized_time,
            morning_enabled=True
        )
        await interaction.response.send_message(
            f"✅ Morgenbegrüßung in {kanal.mention} um **{normalized_time} Uhr** aktiviert.",
            ephemeral=True
        )

    @app_commands.command(
        name="twitch",
        description="Legt den Kanal für Twitch-Livebenachrichtigungen fest."
    )
    async def twitch(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel
    ):
        await update_guild_settings(interaction.guild.id, twitch_channel_id=kanal.id)
        await interaction.response.send_message(
            f"✅ Twitch-Benachrichtigungen werden in {kanal.mention} gesendet.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
