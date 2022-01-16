import re

import discord
import pytz
from discord.ext import commands
from sqlalchemy import select

from common import conf
from common.db import session
from datamodels import genshin_events
from datamodels.guild_settings import GuildSettings, GuildSettingKey


class GenshinCodeScanner(commands.Cog):
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
        if message.channel.id in conf.CODE_CHANNEL_IDS:
            await self.process_message()

    async def process_message(self):
        for code_channel_id in conf.CODE_CHANNEL_IDS:
            source = session.get(genshin_events.EventSource, (code_channel_id,))
            channel = await self.bot.fetch_channel(code_channel_id)
            messages = []
            latest = None

            async for message in channel.history(limit=100):
                if source and message.created_at <= source.read_until.replace(
                    tzinfo=pytz.UTC
                ):
                    break
                if not latest:
                    latest = message.created_at
                messages.append(message)

            if not messages:
                break

            for message in messages:
                raw = message.content + "\n".join(
                    embed.description for embed in message.embeds
                )
                codes = re.findall(r"[A-Z0-9]{12}", raw)
                embed = discord.Embed(
                    description="\n".join(
                        f"[{code}](https://genshin.mihoyo.com/en/gift?code={code})"
                        for code in codes
                    )
                )

                if codes:
                    for code_channel in session.execute(
                        select(GuildSettings).where(
                            GuildSettings.key == GuildSettingKey.CODE_CHANNEL
                        )
                    ).scalars():
                        channel = await self.bot.fetch_channel(code_channel.value)
                        code_role = session.get(
                            GuildSettings,
                            (code_channel.guild_id, GuildSettingKey.CODE_ROLE),
                        )
                        await channel.send(
                            content=f"\n<@&{code_role.value}>" if code_role else None,
                            embed=embed,
                        )

            source = genshin_events.EventSource(
                channel_id=code_channel_id, read_until=latest
            )
            session.merge(source)
            session.commit()
