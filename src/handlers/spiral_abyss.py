import dataclasses
import io

import aiohttp
import discord
from dateutil.parser import parse
from discord.ext import commands
from sqlalchemy import select

from common import guild_level, conf
from common.db import session
from common.genshin_server import ServerEnum
from datamodels.spiral_abyss import SpiralAbyssRotation
from utils.html_parser import HtmlParser
from utils.images import create_image_with_label, create_collage, create_label


@dataclasses.dataclass
class Enemy:
    name: str = ""
    icon_url: str = ""
    count: int = 0


@dataclasses.dataclass
class AbyssChamber:
    name: str = ""
    enemy_level: str = ""
    challenge_target: str = ""
    halves: list[list[Enemy]] = dataclasses.field(default_factory=list)
    image_url: str = None


@dataclasses.dataclass
class AbyssFloor:
    name: str = ""
    ley_line_disorder: str = ""
    additional_effects: str = ""
    chambers: list[AbyssChamber] = dataclasses.field(default_factory=list)


class SpiralAbyssHandler(commands.Cog):
    ABYSS_URL = "https://genshin-impact.fandom.com/wiki/Spiral_Abyss/Floors"

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    async def _create_chamber_image(self, chamber: AbyssChamber) -> bytes:
        async with aiohttp.ClientSession() as session:
            half_images = []
            for i, half in enumerate(chamber.halves):
                enemy_images = []
                for enemy in half:
                    async with session.get(enemy.icon_url) as response:
                        body: bytes = await response.read()
                        image: bytes = create_image_with_label(
                            body, str(enemy.count), resize_to=(50, 50)
                        )
                        enemy_images.append(image)

                half_label = create_label(["First Half", "Second Half"][i])
                half_image = create_collage(6, enemy_images, padding=2)
                half_images += [half_label, half_image]

            return create_collage(1, half_images, padding=4)

    async def get_abyss_lineup(self) -> list[dict]:
        current_time = ServerEnum.NORTH_AMERICA.current_time.replace(tzinfo=None)
        rotations = (
            session.execute(
                select(SpiralAbyssRotation).where(
                    SpiralAbyssRotation.start <= current_time,
                    SpiralAbyssRotation.end >= current_time,
                )
            )
            .scalars()
            .all()
        )

        if rotations:
            return rotations[0].data

        html = HtmlParser(self.ABYSS_URL)
        node = html.xpath('//*[@id="Abyssal_Moon_Spire"]')[0].getparent()
        period = (
            html.xpath("//*[contains(text(),'(Present)')]")[0]
            .text.replace("(Present)", "")
            .strip()
        )

        floors = []

        while node is not None:
            if node.tag == "h4" and "Floor " in node.text_content():
                abyss_floor = AbyssFloor()
                abyss_floor.name = node.text_content()

                while node is not None:
                    node = node.getnext()

                    if node.tag != "ul":
                        break

                    for child in node:
                        text = child[0].text_content()
                        if text == "Ley Line Disorder":
                            abyss_floor.ley_line_disorder = child[1].text_content()
                        elif text == "Additional Effects":
                            abyss_floor.additional_effects = child[1].text_content()

                        elif "Chamber" in text:
                            chamber = AbyssChamber()
                            chamber.name = child[0].text

                            for chamber_detail_node in child[1]:
                                text = chamber_detail_node[0].text
                                if "Enemy Level" in text:
                                    chamber.enemy_level = chamber_detail_node[0].tail
                                elif "Challenge Target" in text:
                                    chamber.challenge_target = chamber_detail_node[
                                        0
                                    ].tail
                                elif "First Half" in text or "Second Half" in text:
                                    enemy_list = []
                                    for enemy_node in chamber_detail_node[1:]:
                                        if "card_with_caption" in enemy_node.classes:
                                            enemy = Enemy()
                                            enemy.icon_url = enemy_node.xpath(
                                                '*/div[@class="card_image"]/a/img'
                                            )[0].attrib["data-src"]
                                            enemy.count = enemy_node.xpath(
                                                '*/div[@class="card_text"]'
                                            )[0].text_content()
                                            enemy.name = enemy_node.xpath(
                                                'div[@class="card_caption"]'
                                            )[0].text_content()
                                            enemy_list.append(enemy)
                                    chamber.halves.append(enemy_list)

                            image = await self._create_chamber_image(chamber)
                            channel = await self.bot.fetch_channel(
                                conf.IMAGE_HOSTING_CHANNEL_ID
                            )
                            message = await channel.send(
                                file=discord.File(
                                    io.BytesIO(image),
                                    filename=f"{abyss_floor.name}-{chamber.name}.png",
                                )
                            )
                            chamber.image_url = message.attachments[0].url

                            abyss_floor.chambers.append(chamber)

                floors.append(abyss_floor)
            else:
                node = node.getnext()

        dates = list(map(parse, period.split("-")))
        rotation = SpiralAbyssRotation(start=dates[0], end=dates[1], data=floors)
        session.add(rotation)
        session.commit()

        return rotation.data

    @commands.slash_command(
        description="Shows abyss lineup",
        guild_ids=guild_level.get_guild_ids(level=1),
    )
    async def abyss(self, ctx):
        await ctx.defer()
        floors = await self.get_abyss_lineup()
        view = AbyssLineupView(ctx=ctx, floor_data=floors)
        await ctx.send_followup(embeds=view.embeds, view=view)


class AbyssLineupButton(discord.ui.Button):
    def __init__(self, delta: int, **kwargs):
        super().__init__(**kwargs)
        self.delta = delta

    async def callback(self, interaction: discord.Interaction):
        self.view.change_chamber(delta=self.delta)
        await interaction.response.edit_message(embeds=self.view.embeds, view=self.view)


class AbyssLineupView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext, floor_data: list[dict]):
        super().__init__(timeout=15 * 60)
        self.ctx = ctx
        self.floor_options = [0, 1, 2, 3]
        self.floor_data = floor_data
        self.chamber = (0, 0)
        self.embeds = []

        self.previous_button = AbyssLineupButton(
            label="< Previous Chamber",
            delta=-1,
            style=discord.ButtonStyle.blurple,
            row=0,
        )
        self.next_button = AbyssLineupButton(
            label="Next Chamber >", delta=1, style=discord.ButtonStyle.blurple, row=0
        )

        self.change_chamber(delta=0)

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.previous_button.disabled = self.chamber == (0, 0)
        self.next_button.disabled = self.chamber == (self.floor_options[-1], 2)
        self.add_item(self.previous_button)
        self.add_item(self.next_button)

        for floor_option in self.floor_options:
            delta = (floor_option - self.chamber[0]) * 3 - self.chamber[1]
            button = AbyssLineupButton(
                label=f"{floor_option + 9}-1",
                delta=delta,
                style=discord.ButtonStyle.gray,
                row=1,
            )
            self.add_item(button)

    def change_chamber(self, delta):
        v = self.chamber[0] * 3 + self.chamber[1] + delta
        self.chamber = v // 3, (v % 3)

        floor = self.floor_data[self.chamber[0]]
        self.embeds = []
        header = discord.Embed(title=floor["name"])
        if floor["ley_line_disorder"]:
            header.add_field(
                name="Ley Line Disorder", value=floor["ley_line_disorder"], inline=False
            )
        if floor["additional_effects"]:
            header.add_field(
                name="Additional Effects",
                value=floor["additional_effects"],
                inline=False,
            )
        self.embeds.append(header)

        chamber = floor["chambers"][self.chamber[1]]
        chamber_embed = discord.Embed(title=chamber["name"])
        chamber_embed.add_field(
            name="Enemy Level",
            value=chamber["enemy_level"],
        )
        chamber_embed.add_field(
            name="Challenge Target",
            value=chamber["challenge_target"],
        )
        chamber_embed.set_image(url=chamber["image_url"])
        self.embeds.append(chamber_embed)

        self.update_buttons()

    async def on_timeout(self) -> None:
        """Disables all buttons when the view times out."""
        for item in self.children:
            item.disabled = True
        message = await self.ctx.interaction.original_message()
        await message.edit(view=self)
