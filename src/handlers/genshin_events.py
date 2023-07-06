import re

import aiohttp
import discord
import pytz
from discord.ext import commands
from sqlalchemy import select

from common import conf
from common.db import session
from datamodels import genshin_events
from datamodels.guild_settings import GuildSettings, GuildSettingKey


class GenshinEventScanner(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            await self.process_message()
            self.start_up = True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id in conf.NEWS_CHANNEL_IDS:
            await self.process_message()

    async def process_message(self):
        async with aiohttp.ClientSession() as httpsession:
            for news_channel_id in conf.NEWS_CHANNEL_IDS:
                source = session.get(genshin_events.EventSource, (news_channel_id,))
                channel = await self.bot.fetch_channel(news_channel_id)
                events = []
                latest = None

                async for message in channel.history(limit=100):
                    if source and message.created_at <= source.read_until.replace(
                        tzinfo=pytz.UTC
                    ):
                        break
                    if not latest:
                        latest = message.created_at
                    for embed in message.embeds:
                        if not embed.description:
                            continue
                        for url in re.findall(
                            r"https://[A-z0-9./?#]+", embed.description
                        ):
                            async with httpsession.get(url) as response:
                                if (
                                    response.url.host == "webstatic-sea.hoyoverse.com"
                                    and response.url.path.startswith("/ys/event/")
                                ):
                                    events.append(
                                        genshin_events.GenshinEvent(
                                            id=response.url.path,
                                            type="web",
                                            description=embed.description,
                                            url=url,
                                            start_time=message.created_at,
                                        )
                                    )

                for event in events:
                    existing = session.get(genshin_events.GenshinEvent, (event.id,))
                    if not existing:
                        session.add(event)
                        for event_channel in session.execute(
                            select(GuildSettings).where(
                                GuildSettings.key == GuildSettingKey.EVENT_CHANNEL
                            )
                        ).scalars():
                            embed = discord.Embed(description=event.description)
                            channel = await self.bot.fetch_channel(event_channel.value)
                            event_role = session.get(
                                GuildSettings,
                                (event_channel.guild_id, GuildSettingKey.EVENT_ROLE),
                            )
                            await channel.send(
                                content=f"\n<@&{event_role.value}>"
                                if event_role
                                else None,
                                embed=embed,
                            )
                        session.commit()

                if latest:
                    source = genshin_events.EventSource(
                        channel_id=news_channel_id, read_until=latest
                    )
                    session.merge(source)
                    session.commit()
