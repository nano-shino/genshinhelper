import re

import discord
from discord import Option
from discord.ext import commands

from common import guild_level


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

        try:
            message = await channel.fetch_message(int(message_id))
        except (ValueError, discord.NotFound):
            await ctx.respond("Bad message_id.", ephemeral=True)
            return

        emotes = re.findall(r'<:(\w*):(\d*)>', message.content)
        animated_emotes = re.findall(r'<a:(\w*):(\d*)>', message.content)
        lines = []
        for emote_name, emote_id in emotes:
            lines += [f"Emote [{emote_name}](https://cdn.discordapp.com/emojis/{emote_id}.png?size=1024)"]
        for emote_name, emote_id in animated_emotes:
            lines += [f"Emote [{emote_name}](https://cdn.discordapp.com/emojis/{emote_id}.gif?size=1024&quality=lossless)"]
        for sticker in message.stickers:
            lines += [f"Sticker [{sticker.name}](https://media.discordapp.net/stickers/{sticker.id}.png?size=1024)"]

        if not lines:
            await ctx.respond("No emotes found.", ephemeral=True)
            return

        await ctx.respond(embed=discord.Embed(description="\n".join(lines)), ephemeral=True)
