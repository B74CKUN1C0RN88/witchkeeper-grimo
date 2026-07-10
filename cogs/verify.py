from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from settings_store import get_guild_settings


class VerifyView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verifizieren",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="grimo_multiserver_verify",
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Dieser Button funktioniert nur auf einem Server.",
                ephemeral=True,
            )
            return

        settings = await get_guild_settings(interaction.guild.id)
        role_id = settings["verify_role_id"]
        role = interaction.guild.get_role(role_id) if role_id else None

        if role is None:
            await interaction.response.send_message(
                "Auf diesem Server wurde noch keine Verifizierungsrolle eingerichtet. "
                "Ein Administrator muss `/setup verifizierung` benutzen.",
                ephemeral=True,
            )
            return

        if role in interaction.user.roles:
            await interaction.response.send_message(
                "Du bist bereits verifiziert.",
                ephemeral=True,
            )
            return

        try:
            await interaction.user.add_roles(
                role,
                reason="Verifizierung über Grimo",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Ich darf diese Rolle nicht vergeben. Meine Bot-Rolle muss "
                "über der Verifizierungsrolle stehen und „Rollen verwalten“ besitzen.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            print(f"[Verifizierung] Discord-Fehler: {error}")
            await interaction.response.send_message(
                "Die Rolle konnte wegen eines Discord-Fehlers nicht vergeben werden.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ Du wurdest verifiziert und hast jetzt {role.mention}.",
            ephemeral=True,
        )


class VerifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="verification",
        description="Sendet das Verifizierungsfeld in diesen Kanal.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def verification(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Dieser Befehl funktioniert nur auf einem Server.",
                ephemeral=True,
            )
            return

        settings = await get_guild_settings(interaction.guild.id)
        role_id = settings["verify_role_id"]
        role = interaction.guild.get_role(role_id) if role_id else None

        if role is None:
            await interaction.response.send_message(
                "Richte zuerst mit `/setup verifizierung` eine Rolle ein.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="✅ Verifizierung",
            description=(
                "Willkommen auf unserem Server!\n\n"
                "Klicke auf **Verifizieren**, um Zugriff zu erhalten "
                f"und die Rolle {role.mention} zu bekommen."
            ),
            color=discord.Color.purple(),
        )
        embed.set_footer(text="Grimo • Verifizierung")

        await interaction.response.send_message(
            embed=embed,
            view=VerifyView(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VerifyCog(bot))
