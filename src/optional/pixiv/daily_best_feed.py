import asyncio
import datetime
import os
import tempfile

import discord
from dateutil.relativedelta import relativedelta
from discord.ext import commands, tasks
from pixivpy3 import AppPixivAPI

from common import conf
from common.db import session
from common.logging import logger
from optional.pixiv.illust_model import Illust


class DailyBestIllustFeed(commands.Cog):
    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False
        self.api = AppPixivAPI()
        self.blocked_tags = []
        self.model = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            self.start_up = True
            self.api.auth(refresh_token=conf.PIXIV_REFRESH_TOKEN)
            self.blocked_tags = set(conf.PIXIV_BLOCKED_TAGS)
            self.job.start()

    @tasks.loop(hours=8)
    async def job(self):
        logger.info(f"Checking Pixiv")
        result = self.api.search_illust(
            "原神",
            search_target="partial_match_for_tags",
            sort="date_asc",
            start_date=(datetime.datetime.today() - relativedelta(days=3)).strftime("%Y-%m-%d"),
            end_date=datetime.datetime.today().strftime("%Y-%m-%d"))

        feed_channel = await self.bot.fetch_channel(conf.PIXIV_CHANNEL_ID)
        most_popular = []
        for page in range(200):
            logger.info(f"Fetching Pixiv page {page}")
            for illust in result.illusts:
                try:
                    if illust.x_restrict or illust.sanity_level > 3 or illust.total_bookmarks < 1000:
                        continue
                    has_blocked_tag = any(word in self.blocked_tags
                                          for tag in illust.tags
                                          for word in (tag.name + " " + (tag.translated_name or "")).split())
                    most_popular.append(illust)

                    record = session.get(Illust, (illust.id))
                    if not record:
                        filepath, ext = os.path.splitext(illust.image_urls.large)

                        with tempfile.NamedTemporaryFile(suffix=ext) as tmp:
                            image_url = illust.image_urls.large
                            self.api.download(image_url, fname=tmp)
                            url = f"https://www.pixiv.net/en/artworks/{illust.id}"
                            logger.info(f"Send to feed channel: {url}")
                            if has_blocked_tag:
                                await feed_channel.send(f"||{url}||")
                            else:
                                embed = discord.Embed(
                                    title=illust.title,
                                    description=url)
                                embed.set_author(name=illust.user.name)
                                file = discord.File(tmp.name, filename=f"{illust.id}.png")
                                embed.set_image(url=f"attachment://{illust.id}.png")
                                await feed_channel.send(embed=embed, file=file)

                        new_record = Illust(id=illust.id)
                        session.add(new_record)
                        session.commit()
                except Exception:
                    logger.exception(illust)

            next_qs = self.api.parse_qs(result.next_url)
            if next_qs is None:
                break

            result = self.api.search_illust(**next_qs)
            await asyncio.sleep(1)
        else:
            logger.warn("Loop ends without expected break (Too many illusts)")

        logger.info(f"Found {len(most_popular)} illusts with given filters")
