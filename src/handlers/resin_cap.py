import asyncio
import logging
import random
from datetime import datetime

import discord
import genshin
from discord.ext import tasks, commands
from sqlalchemy import select

from common.db import session
from datamodels.account_settings import Preferences
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem, ItemType


class ResinCapReminder(commands.Cog):
    DATABASE_KEY = ItemType.RESIN_CAP  # Key to query from reminder table
    CHECK_INTERVAL = 60 * 60 * 3  # Query Mihoyo for resin data every 3 hours
    DATA_LAG = 60 * 1  # Wait for 1 minute to confirm resin is capped

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            await asyncio.sleep(
                random.randint(3 * 60, 5 * 60)
            )  # sleep randomly so everything doesn't start up at once.
            self.job.start()
            self.start_up = True

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def job(self):
        for discord_id in session.execute(
            select(GenshinUser.discord_id.distinct())
        ).scalars():
            try:
                await self.check_resin(discord_id)
            except Exception:
                logging.exception(f"Cannot check resin for {discord_id}")

    async def check_resin(
        self, discord_id: int, max_time_awaited: float = CHECK_INTERVAL
    ):
        min_remaining_time = 60 * 60 * 24 * 7

        for account in session.execute(
            select(GenshinUser).where(GenshinUser.discord_id == discord_id)
        ).scalars():
            if not account.settings[Preferences.RESIN_REMINDER]:
                return

            gs: genshin.GenshinClient = account.client
            capped_uids = []

            for uid in account.genshin_uids:
                notes = await gs.get_notes(uid)
                reminder = session.get(ScheduledItem, (uid, self.DATABASE_KEY))

                if notes.current_resin == notes.max_resin:
                    if not reminder:
                        capped_uids.append(str(uid))
                else:
                    if reminder:
                        session.delete(reminder)
                        session.commit()
                    min_remaining_time = min(
                        min_remaining_time,
                        (
                            notes.resin_recovered_at - datetime.now().astimezone()
                        ).total_seconds(),
                    )

            if capped_uids:
                discord_user = await self.bot.fetch_user(discord_id)
                channel = await discord_user.create_dm()
                embed = discord.Embed(
                    title="Your resin is capped!",
                    description=f"UID: {', '.join(capped_uids)}",
                    color=0xFF1100,
                )
                embed.set_footer(text="You can turn this notification off via settings")
                await channel.send(embed=embed)
                for uid in capped_uids:
                    session.merge(
                        ScheduledItem(
                            id=uid,
                            type=self.DATABASE_KEY,
                            scheduled_at=datetime.utcnow(),
                            done=True,
                        )
                    )
                session.commit()

            await gs.close()

        await_time = min_remaining_time
        if await_time < max_time_awaited:
            logging.info(f"Checking again for {discord_id} in {await_time} seconds")
            await asyncio.sleep(await_time)
            await self.check_resin(discord_id, max_time_awaited - await_time)
