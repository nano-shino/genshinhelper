import enum

import discord
from discord import SlashCommandGroup, Option
from discord.ext import commands
from discord.ext.commands import has_permissions

from common import conf
from common.db import session
from datamodels.guild_settings import GuildSettings


class GuildSettingKey(enum.Enum):
    BOT_CHANNEL = "bot_channel"


setting_autocomplete = discord.utils.basic_autocomplete([e.value for e in GuildSettingKey])


class GuildSettingManager(commands.Cog):
    key_set = set(e.value for e in GuildSettingKey)
    guild = SlashCommandGroup(
        "guild",
        "Guild-related commands",
        guild_ids=conf.DISCORD_GUILD_IDS)

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    def set_entry(self, guild_id: int, key: str, value: str):
        session.add(GuildSettings(guild_id=guild_id, key=key, value=value))
        session.commit()

    def get_entry(self, guild_id: int, key: str):
        row = session.get(GuildSettings, (guild_id, key))
        return row.value if row else None

    @guild.command(
        description="Set guild config"
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
