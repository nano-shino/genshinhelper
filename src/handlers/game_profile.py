import asyncio
import io

import discord
from discord import Option
from discord.ext import commands
from discord.ui import View, Select, Button
from enkacard import encbanner
from enkacard.encbanner import Akasha
from enkacard.src.generator import teample_two
from enkanetwork import EnkaNetworkAPI, EnkaNetworkResponse

from common.autocomplete import get_uid_suggestions
from handlers import base_handler


class GameCharacterDropdown(Select):
    def __init__(self, enkanetwork_resp: EnkaNetworkResponse, akasha_ranking: bool):
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
        super().__init__(placeholder='Choose a character to create card...', min_values=1, max_values=1, options=options)

        self.tasks = {}
        asyncio.create_task(self.load_card_images(akasha_ranking))

    async def load_card_images(self, akasha_ranking: bool):
        async def create_art(cards_dict, key, art, setting, template):
            cards_dict[key.id] = await teample_two.Creat(
                key, encard.translateLang, art, encard.hide_uid, encard.uid,
                encard.enc.player.nickname, setting).start(False)
            if akasha_ranking:
                cards_dict[key.id] = await Akasha(encard.uid).start(cards_dict[key.id], template)

        async with encbanner.ENC(uid=self.enkanetwork_resp.uid) as encard:
            template = 2

            generator = []
            gen_tools = []

            if encard.pickle["get_generate"]:
                generator = await encard.pickle_class.get_generator(template)

            for key in encard.enc.characters:
                encard.character_ids.append(key.id)
                encard.character_name.append(key.name)

                if encard.character_id:
                    if not str(key.id) in encard.character_id:
                        continue

                if key.id in generator:
                    if not generator.get(key.id, None) is None:
                        gen_tools.append(generator.get(key.id))
                    continue

                if str(key.id) == "10000092":
                    key.image.banner.url = "https://api.ambr.top/assets/UI/UI_Gacha_AvatarImg_Gaming.png"
                elif str(key.id) == "10000093":
                    key.image.banner.url = "https://api.ambr.top/assets/UI/UI_Gacha_AvatarImg_Liuyun.png"

                art = None
                setting = 0

                if encard.character_art:
                    if str(key.id) in encard.character_art:
                        art = encard.character_art[str(key.id)]

                if encard.setting_art:
                    if str(key.id) in encard.setting_art:
                        setting = encard.setting_art[str(key.id)]

                if not encard.character_id is None:
                    if not str(key.id) in encard.character_id:
                        continue

                self.tasks[key.id] = asyncio.create_task(create_art(self.cards, key, art, setting, template))

        await asyncio.gather(*self.tasks.values())

    async def callback(self, interaction: discord.Interaction):
        if not self.cards:
            self.placeholder = "Creating character card... (first load is longer)"
        else:
            self.placeholder = "Creating character card..."

        await interaction.response.edit_message(view=self.view)

        character_id = int(self.values[0])
        await self.tasks[character_id]
        self.placeholder = "Choose another character to create card..."

        character = self.cards[character_id]

        if len(self.view.message.attachments) >= 9:
            self.view.remove_item(self)  # Remove dropdown as discord doesn't allow more than 10 images

        with io.BytesIO() as image_binary:
            character['card'].save(image_binary, 'PNG')
            image_binary.seek(0)

            response = await interaction.original_response()
            await response.edit(
                file=discord.File(image_binary, f"{character['name']}.png"), view=self.view)


class GameProfileView(View):
    def __init__(self, ctx: discord.ApplicationContext, enkanetwork_resp: EnkaNetworkResponse, akasha_ranking: bool):
        super().__init__(timeout=15 * 60)
        self.ctx = ctx
        self.add_item(GameCharacterDropdown(enkanetwork_resp, akasha_ranking))
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

        intro_embed = await self.create_intro_embed(data)
        embeds = [intro_embed]

        if not data.characters:
            embeds.append(discord.Embed(
                description="Please enable the **Show Character Details** option in your "
                            "Character Showcase in-game to see the details."))
            await ctx.send_followup(embeds=embeds)
        else:
            view = GameProfileView(ctx=ctx, enkanetwork_resp=data, akasha_ranking=False)
            await ctx.send_followup(embeds=embeds, view=view)

    async def create_intro_embed(self, data: EnkaNetworkResponse):
        embed = discord.Embed(
            description=f"{data.player.signature}"
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
