import asyncio
import logging
import random
from datetime import datetime

import discord
import genshin
from discord.ext import tasks, commands
from sqlalchemy import select

from common.constants import Preferences
from common.db import session
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem, ItemType


class ResinCapReminder(commands.Cog):
    RESIN_KEY = ItemType.RESIN_CAP  # Check if user enabled resin notification
    TEAPOT_KEY = ItemType.TEAPOT_CAP  # Check if user enabled teapot notification
    CHECK_INTERVAL = 60 * 60 * 3  # Query Mihoyo for resin data every 3 hours
    TEAPOT_CHECK_INTERVAL = 60 * 60 * 6  # Query Mihoyo for teapot data every 6 hours

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            await asyncio.sleep(
                random.randint(3 * 60, 5 * 60)
            )  # sleep randomly so everything doesn't start up at once.
            self.resin_job.start()
            self.teapot_job.start()
            self.start_up = True

    @tasks.loop(seconds=CHECK_INTERVAL, reconnect=False)
    async def resin_job(self):
        for discord_id in session.execute(
            select(GenshinUser.discord_id.distinct())
        ).scalars():
            try:
                await self.check_resin(discord_id)
            except Exception:
                logging.exception(f"Cannot check resin for {discord_id}")

    @tasks.loop(seconds=TEAPOT_CHECK_INTERVAL, reconnect=False)
    async def teapot_job(self):
        for discord_id in session.execute(
            select(GenshinUser.discord_id.distinct())
        ).scalars():
            try:
                await self.check_teapot(discord_id)
            except Exception:
                logging.exception(f"Cannot check teapot for {discord_id}")

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
                reminder = session.get(ScheduledItem, (uid, self.RESIN_KEY))

                if notes.current_resin == notes.max_resin:
                    if not reminder:
                        capped_uids.append(str(uid))
                else:
                    if reminder:
                        session.delete(reminder)
                        session.commit()
                    min_remaining_time = min(min_remaining_time, notes.until_resin_recovery)

            if capped_uids:
                discord_user = await self.bot.fetch_user(discord_id)
                channel = await discord_user.create_dm()
                embed = discord.Embed(
                    title="Your resin is capped!",
                    description=f"UID: {', '.join(capped_uids)}",
                    color=0xFF1100,
                )
                embed.set_footer(text="You can turn this notification off via /user settings")
                await channel.send(embed=embed)
                for uid in capped_uids:
                    session.merge(
                        ScheduledItem(
                            id=uid,
                            type=self.RESIN_KEY,
                            scheduled_at=datetime.utcnow(),
                            done=True,
                        )
                    )
                session.commit()

            await gs.close()

        await_time = min_remaining_time
        if 0 < await_time < max_time_awaited:
            logging.info(f"Checking again for {discord_id} in {await_time} seconds")
            await asyncio.sleep(await_time)
            await self.check_resin(discord_id, max_time_awaited - await_time)

    async def check_teapot(
        self, discord_id: int, max_time_awaited: float = TEAPOT_CHECK_INTERVAL
    ):
        min_remaining_time = 60 * 60 * 24 * 7

        for account in session.execute(
            select(GenshinUser).where(GenshinUser.discord_id == discord_id)
        ).scalars():
            if not account.settings[Preferences.TEAPOT_REMINDER]:
                return

            gs: genshin.GenshinClient = account.client
            capped_uids = []

            for uid in account.genshin_uids:
                notes = await gs.get_notes(uid)
                reminder = session.get(ScheduledItem, (uid, self.TEAPOT_KEY))

                if notes.current_realm_currency == notes.max_realm_currency:
                    if not reminder:
                        capped_uids.append(str(uid))
                else:
                    if reminder:
                        session.delete(reminder)
                        session.commit()
                    min_remaining_time = min(min_remaining_time, notes.until_realm_currency_recovery)

            if capped_uids:
                discord_user = await self.bot.fetch_user(discord_id)
                channel = await discord_user.create_dm()
                embed = discord.Embed(
                    title="Your teapot currency is capped!",
                    description=f"UID: {', '.join(capped_uids)}",
                    color=0xFF1100,
                )
                embed.set_thumbnail(
                    url="https://static.wikia.nocookie.net/gensin-impact/images/5/5a/Item_Serenitea_Pot.png")
                embed.set_footer(text="You can turn this notification off via /user settings")
                await channel.send(embed=embed)
                for uid in capped_uids:
                    session.merge(
                        ScheduledItem(
                            id=uid,
                            type=self.TEAPOT_KEY,
                            scheduled_at=datetime.utcnow(),
                            done=True,
                        )
                    )
                session.commit()

            await gs.close()

        await_time = min_remaining_time
        if 0 < await_time < max_time_awaited:
            logging.info(f"Checking again for {discord_id} in {await_time} seconds")
            await asyncio.sleep(await_time)
            await self.check_teapot(discord_id, max_time_awaited - await_time)
