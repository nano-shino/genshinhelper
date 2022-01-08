import re

import discord
from discord import SlashCommandGroup, Option
from discord.ext import commands
from discord.ext.commands import has_permissions

from common import guild_level, autocomplete
from common.db import session
from datamodels.guild_settings import GuildSettings, ALL_KEYS


class EmoteHandler(commands.Cog):

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @commands.slash_command(
        description="Extracts all the urls from a message",
        guild_ids=guild_level.get_guild_ids(level=2)
    )
    async def emotes(
            self,
            ctx: discord.ApplicationContext,
            message_id: Option(str, "The ID of the message that contains the emotes or stickers"),
    ):
        channel = await self.bot.fetch_channel(ctx.channel_id)
        message = await channel.fetch_message(int(message_id))
        emotes = re.findall(r'<:(\w*):(\d*)>', message.content)
        lines = []
        for emote_name, emote_id in emotes:
            lines += [f"[{emote_name}](https://cdn.discordapp.com/emojis/{emote_id}.png?size=1024)"]
        for sticker in message.stickers:
            lines += [f"[{sticker.name}](https://media.discordapp.net/stickers/{sticker.id}.png?size=1024)"]
        await ctx.respond(embed=discord.Embed(description="\n".join(lines)), ephemeral=True)
