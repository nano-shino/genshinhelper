import discord
from discord import SlashCommandGroup, Option
from discord.ext import commands
from discord.ext.commands import has_permissions

from common import guild_level, autocomplete
from common.db import session
from datamodels.guild_settings import GuildSettings, ALL_KEYS

setting_autocomplete = autocomplete.fuzzy_autocomplete(list(ALL_KEYS.values()))


class GuildSettingManager(commands.Cog):
    key_set = set(ALL_KEYS.values())
    guild = SlashCommandGroup(
        "guild",
        "Guild-related commands",
        guild_ids=guild_level.get_guild_ids(level=1))

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    def set_entry(self, guild_id: int, key: str, value: str):
        session.merge(GuildSettings(guild_id=guild_id, key=key, value=value))
        session.commit()

    def get_entry(self, guild_id: int, key: str):
        row = session.get(GuildSettings, (guild_id, key))
        return row.value if row else None

    @guild.command(
        description="Sets guild config [admin-only]"
    )
    @has_permissions(administrator=True)
    async def set(
            self,
            ctx,
            key: Option(str, "Key", autocomplete=setting_autocomplete),
            value
    ):
        if key not in self.key_set:
            await ctx.respond("Not a valid key", ephemeral=True)
            return

        self.set_entry(ctx.guild_id, key, value)
        await ctx.respond("Value set successfully", ephemeral=True)
