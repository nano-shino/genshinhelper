import asyncio
import io

import discord
from discord import Option
from discord.ext import commands
from discord.ui import View, Select, Button
from enkacard import encbanner
from enkanetwork import EnkaNetworkAPI, EnkaNetworkResponse

from common import guild_level
from common.autocomplete import get_uid_suggestions
from handlers import base_handler


class GameCharacterDropdown(Select):
    def __init__(self, enkanetwork_resp: EnkaNetworkResponse):
        self.enkanetwork_resp = enkanetwork_resp
        self.cards = {}

        options = [
            discord.SelectOption(
                label=f"{character.name} {character.rarity}★"
                      f" - C{character.constellations_unlocked} {character.level}/{character.max_level}"
                      f" - {'/'.join(str(skill.level) for skill in character.skills)}",
                value=str(character.id))
            for character in enkanetwork_resp.characters
        ]
        super().__init__(placeholder='Choose a character to view card...', min_values=1, max_values=1, options=options)

        self.load_image_task = asyncio.create_task(self.load_card_images())

    async def load_card_images(self):
        async with encbanner.ENC(uid=self.enkanetwork_resp.uid) as encard:
            self.cards = (await encard.creat()).card

    async def callback(self, interaction: discord.Interaction):
        await self.load_image_task

        character = next(card for card in self.cards if card.id == int(self.values[0]))

        if len(self.view.message.attachments) >= 9:
            self.view.remove_item(self)  # Remove dropdown as discord doesn't allow more than 10 images

        with io.BytesIO() as image_binary:
            character.card.save(image_binary, 'PNG')
            image_binary.seek(0)

            await interaction.response.edit_message(
                file=discord.File(image_binary, f'{character.name}.png'), view=self.view)


class GameProfileView(View):
    def __init__(self, ctx: discord.ApplicationContext, enkanetwork_resp: EnkaNetworkResponse):
        super().__init__(timeout=15 * 60)
        self.ctx = ctx
        self.add_item(GameCharacterDropdown(enkanetwork_resp))
        uid = enkanetwork_resp.uid
        self.add_item(Button(
            label="View on EnkaNetwork", style=discord.ButtonStyle.link, url=f"https://enka.network/u/{uid}/"))
        self.add_item(Button(
            label="View on Akasha", style=discord.ButtonStyle.link, url=f"https://akasha.cv/profile/{uid}"))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        message = await self.ctx.interaction.original_message()
        await message.edit(view=self)


class GameProfileHandler(base_handler.BaseHandler):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @commands.slash_command(
        description="Show game profile",
        guild_ids=guild_level.get_guild_ids(level=3),
    )
    async def profile(
            self,
            ctx,
            uid: Option(str, "Genshin UID", name="uid", autocomplete=get_uid_suggestions),
    ):
        await ctx.defer()

        uid = uid or self.get_default_uid(ctx)
        if not uid:
            await ctx.respond("Please provide a UID")
            return

        client = EnkaNetworkAPI()
        data = await client.fetch_user(int(uid))
        embed = await self.create_intro_embed(data)

        view = GameProfileView(ctx=ctx, enkanetwork_resp=data)
        await ctx.send_followup(embeds=[embed], view=view)

    async def create_intro_embed(self, data: EnkaNetworkResponse):
        embed = discord.Embed(
            description=f"{data.player.signature}",
            color=discord.Color.blue()
        )

        # Adding fields to the embed
        embed.add_field(name="Level", value=str(data.player.level), inline=True)
        embed.add_field(name="Achievements", value=str(data.player.achievement), inline=True)
        embed.add_field(name="Abyss Progress",
                        value=f"{data.player.abyss_floor} - {data.player.abyss_room}",
                        inline=False)

        # Setting the author icon (player's avatar)
        embed.set_author(name=data.player.nickname, icon_url=data.player.avatar.icon.url)

        return embed
