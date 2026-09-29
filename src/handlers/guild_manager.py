import discord
from discord import SlashCommandGroup, Option
from discord.ext import commands
from discord.ext.commands import has_permissions
from sqlalchemy import delete

from common import guild_level, autocomplete
from common.db import session
from datamodels.guild_settings import GuildSettings, ALL_KEYS

setting_autocomplete = autocomplete.fuzzy_autocomplete(list(ALL_KEYS.values()))


class GuildSettingManager(commands.Cog):
    key_set = set(ALL_KEYS.values())
    guild = SlashCommandGroup(
        "guild", "Guild-related commands", guild_ids=guild_level.get_guild_ids(level=1)
    )

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    def get_entry(self, guild_id: int, key: str):
        row = session.get(GuildSettings, (guild_id, key))
        return row.value if row else None

    @guild.command(description="Gets guild config [admin-only]")
    @has_permissions(administrator=True)
    async def get(
        self,
        ctx,
        key: Option(str, "Key", autocomplete=setting_autocomplete),
    ):
        if key not in self.key_set:
            await ctx.respond("Not a valid key", ephemeral=True)
            return

        value = self.get_entry(ctx.guild_id, key)

        if value is None:
            await ctx.respond(f"No value configured for `{key}`.", ephemeral=True)
        else:
            await ctx.respond(f"**{key}**: `{value}`", ephemeral=True)

    @guild.command(description="Sets guild config [admin-only]")
    @has_permissions(administrator=True)
    async def set(
        self,
        ctx,
        key: Option(str, "Key", autocomplete=setting_autocomplete),
        value: Option(str, "Value (omit this option to remove key)", required=False),
    ):
        if key not in self.key_set:
            await ctx.respond("Not a valid key", ephemeral=True)
            return

        if value is not None:
            session.merge(GuildSettings(guild_id=ctx.guild_id, key=key, value=value))
        else:
            session.execute(
                delete(GuildSettings).where(
                    GuildSettings.guild_id == ctx.guild_id, GuildSettings.key == key
                )
            )

        session.commit()

        await ctx.respond("Value set successfully", ephemeral=True)
