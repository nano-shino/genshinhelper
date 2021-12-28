import enum

import discord
from discord import SlashCommandGroup, Option
from discord.ext import commands
from discord.ext.commands import has_permissions

from common import conf
from common.db import conn


class GuildSettings(enum.Enum):
    BOT_CHANNEL = "bot_channel"


async def setting_autocomplete(ctx: discord.AutocompleteContext):
    return [e.value for e in GuildSettings]


class GuildSettingManager(commands.Cog):

    guild = SlashCommandGroup(
        "guild",
        "Guild-related commands",
        guild_ids=conf.DISCORD_GUILD_IDS)

    def __init__(self, bot: discord.Bot = None):
        with conn:
            conn.execute("create table if not exists guildsettings ("
                         "  guild_id integer not null,"
                         "  key text not null,"
                         "  value text,"
                         "  primary key (guild_id, key)"
                         ")")

    def set_entry(self, guild_id: int, key: str, value: str):
        with conn:
            conn.execute("insert or replace into guildsettings values (?, ?, ?)", (guild_id, key, value))

    def get_entry(self, guild_id: int, key: str):
        with conn:
            result = conn.execute("select value from guildsettings where guild_id=? and key=?", (guild_id, key)).fetchone()
            if result:
                return result[0]

    @guild.command(
        description="Set guild config",
        guild_ids=conf.DISCORD_GUILD_IDS
    )
    @has_permissions(administrator=True)
    async def set(
        self,
        ctx,
        key: Option(str, "Key", autocomplete=setting_autocomplete),
        value
    ):
        self.set_entry(ctx.guild_id, key, value)
        await ctx.respond("Value set successfully", ephemeral=True)
