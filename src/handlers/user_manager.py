import discord
from discord import SlashCommandGroup
from discord.ext import commands

from common import conf


class UserManager(commands.Cog):
    user = SlashCommandGroup(
        "user",
        "User-related commands",
        guild_ids=conf.DISCORD_GUILD_IDS)

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    # def set_entry(
    #         self,
    #         discord_id: int,
    #         mihoyo_id: int,
    #         mihoyo_token: Optional[str],
    #         hoyolab_token: Optional[str],
    #         genshin_uid: Optional[int],
    # ):
    #     with conn:
    #         conn.execute("insert or replace into genshin_user values (?, ?, ?, ?, ?)",
    #                      (discord_id, mihoyo_id, mihoyo_token, hoyolab_token, genshin_uid))
    #
    # def get_entry(self, discord_id: int, mihoyo_id: int):
    #     with conn:
    #         result = conn.execute("select value from genshin_user where discord_id=? and mihoyo_id=?",
    #                               (discord_id, mihoyo_id)).fetchone()
    #         return result[0] if result else None
    #
    # @guild.command(
    #     description="Set guild config",
    #     guild_ids=conf.DISCORD_GUILD_IDS
    # )
    # @has_permissions(administrator=True)
    # async def set(
    #         self,
    #         ctx,
    #         key: Option(str, "Key", autocomplete=setting_autocomplete),
    #         value
    # ):
    #     self.set_entry(ctx.guild_id, key, value)
