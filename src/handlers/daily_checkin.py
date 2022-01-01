import logging
from typing import Optional

import discord
import genshin
from discord.ext import tasks, commands
from genshin.models import DailyReward
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential

from common.db import session
from common.genshin_server import ServerEnum
from common.logging import logger
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem, ItemType


class HoyolabDailyCheckin(commands.Cog):
    DATABASE_KEY = ItemType.DAILY_CHECKIN

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            self.job.start()
            self.start_up = True

    @tasks.loop(hours=4)
    async def job(self):
        for discord_id in session.execute(select(GenshinUser.discord_id.distinct())).scalars():
            discord_user = await self.bot.fetch_user(discord_id)
            channel = await discord_user.create_dm()
            try:
                await self.checkin(discord_id, channel)
            except Exception:
                logging.exception(f"Cannot check in for {discord_id}")

    async def checkin(self, discord_id: int, channel: discord.DMChannel):
        embeds = []

        for account in session.execute(select(GenshinUser).where(GenshinUser.discord_id == discord_id)).scalars():
            gs: genshin.GenshinClient = account.client
            checkin_timezone = ServerEnum.ASIA

            task: ScheduledItem = session.get(ScheduledItem, (account.mihoyo_id, self.DATABASE_KEY))

            if not task or task.scheduled_at < checkin_timezone.day_beginning.replace(tzinfo=None):
                try:
                    reward = await self.claim_reward(gs)
                except Exception:
                    logger.exception("Cannot claim daily rewards")
                    continue

                if reward is not None:
                    embed = discord.Embed()
                    embed.description = f"Claimed daily reward - {reward.amount}x {reward.name} " \
                                        f"| Hoyolab ID {account.mihoyo_id}"
                    embeds.append(embed)

                session.merge(ScheduledItem(
                    id=account.mihoyo_id,
                    type=self.DATABASE_KEY,
                    scheduled_at=checkin_timezone.day_beginning,
                    done=True))
                session.commit()

            await gs.close()

        if embeds:
            await channel.send("I've gone ahead and checked in for you. Have a nice day!", embeds=embeds)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=600))
    async def claim_reward(self, client: genshin.GenshinClient) -> Optional[DailyReward]:
        try:
            return await client.claim_daily_reward(reward=True)
        except genshin.errors.AlreadyClaimed:
            return None
