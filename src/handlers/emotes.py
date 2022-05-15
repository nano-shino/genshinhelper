import io
import re
from dataclasses import dataclass, field
from typing import List

import aiohttp
import discord
from discord.ext import commands


@dataclass
class Emote:
    name: str
    url: str
    image: bytes


@dataclass
class Sticker:
    name: str
    url: str
    image: bytes


@dataclass
class MessageContent:
    emotes: List[Emote] = field(default_factory=list)
    stickers: List[Sticker] = field(default_factory=list)


class EmoteHandler(commands.Cog):
    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @commands.command()
    async def yoink(self, ctx: commands.Context):
        if not ctx.message.reference:
            return

        message = ctx.message.reference.resolved

        if not isinstance(message, discord.Message):
            return

        content = await self.parse_message(message)

        lines = []
        for item in content.emotes + content.stickers:
            lines.append(f"[{item.name}]({item.url})")

        member = await ctx.guild.fetch_member(ctx.author.id)
        if ctx.guild.get_member(self.bot.user.id).guild_permissions.manage_emojis_and_stickers and \
                member.guild_permissions.manage_emojis_and_stickers:
            view = AddView(ctx, content)
            view.message = await ctx.send(embed=discord.Embed(description="\n".join(lines)), view=view)
        else:
            await ctx.send(embed=discord.Embed(description="\n".join(lines)))

    async def parse_message(self, message: discord.Message) -> MessageContent:
        emotes = re.findall(r"<:(\w*):(\d*)>", message.content)
        animated_emotes = re.findall(r"<a:(\w*):(\d*)>", message.content)

        content = MessageContent()
        for emote_name, emote_id in emotes:
            image_url = f"https://cdn.discordapp.com/emojis/{emote_id}.png?size=1024"
            image = await self.get_remote_file(image_url)
            content.emotes.append(Emote(name=emote_name, url=image_url, image=image))
        for emote_name, emote_id in animated_emotes:
            image_url = f"https://cdn.discordapp.com/emojis/{emote_id}.gif?size=1024&quality=lossless"
            image = await self.get_remote_file(image_url)
            content.emotes.append(Emote(name=emote_name, url=image_url, image=image))
        for sticker in message.stickers:
            sticker_url = f"https://media.discordapp.net/stickers/{sticker.id}.png?size=1024"
            image = await self.get_remote_file(sticker_url)
            content.stickers.append(Sticker(name=sticker.name, url=sticker_url, image=image))
        return content

    async def get_remote_file(self, url: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.read()


class AddView(discord.ui.View):
    def __init__(self, ctx: commands.Context, content: MessageContent):
        super().__init__()
        self.ctx = ctx
        self.content = content
        self.message = None

    @discord.ui.button(label="Would you like to add this to your server?", style=discord.ButtonStyle.green)
    async def add(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        member = await self.ctx.guild.fetch_member(interaction.user.id)
        if not member.guild_permissions.manage_emojis_and_stickers:
            await interaction.response.send_message(
                "You don't have permissions to add emojis and stickers", delete_after=10)
            return

        await self.on_timeout()

        reason = f"Requested by {interaction.user.name}"
        for emote in self.content.emotes:
            await self.ctx.guild.create_custom_emoji(name=emote.name, image=emote.image, reason=reason)
        for sticker in self.content.stickers:
            await self.ctx.guild.create_sticker(
                name=sticker.name, file=discord.File(io.BytesIO(sticker.image)),
                emoji=":computer:", description=reason, reason=reason)

    async def on_timeout(self) -> None:
        await self.message.edit(view=None)
