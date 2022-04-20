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
    CHECK_INTERVAL = 60 * 60 * 3  # Query Mihoyo for note data every 3 hours

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            await asyncio.sleep(
                random.randint(0, 60)
            )  # sleep randomly so everything doesn't start up at once.
            self.periodic_check.start()
            self.start_up = True

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def periodic_check(self):
        logging.info("Begin periodic resin check")

        tasks = []
        for discord_id in session.execute(
            select(GenshinUser.discord_id.distinct())
        ).scalars():
            tasks.append(asyncio.create_task(self.check_accounts(discord_id)))

        try:
            await asyncio.gather(*tasks)
        except Exception:
            logging.exception("Failure to check resin data")

    async def check_accounts(self, discord_id: int):
        tasks = []

        for account in session.execute(
            select(GenshinUser).where(GenshinUser.discord_id == discord_id)
        ).scalars():
            teapot_reminder = account.settings[Preferences.TEAPOT_REMINDER]
            resin_reminder = account.settings[Preferences.RESIN_REMINDER]

            if not teapot_reminder and not resin_reminder:
                continue

            gs: genshin.GenshinClient = account.client

            for uid in account.genshin_uids:
                try:
                    notes = await gs.get_notes(uid)

                    if resin_reminder and notes.max_resin > 0:
                        reminder = session.get(ScheduledItem, (uid, self.RESIN_KEY))

                        if reminder:
                            if notes.until_resin_recovery > 0:
                                session.delete(reminder)
                                session.commit()
                                reminder = None

                        if not reminder and notes.until_resin_recovery < self.CHECK_INTERVAL:
                            tasks.append(
                                asyncio.create_task(
                                    self.notify_resin(account, uid, notes.until_resin_recovery + 60)
                                )
                            )

                    if teapot_reminder and notes.max_realm_currency > 0:
                        reminder = session.get(ScheduledItem, (uid, self.TEAPOT_KEY))

                        if reminder:
                            if notes.until_realm_currency_recovery > 0:
                                session.delete(reminder)
                                session.commit()
                                reminder = None

                        # "greater than 0" to prevent a bug where current coins = max coins
                        if not reminder and 0 < notes.until_realm_currency_recovery < self.CHECK_INTERVAL:
                            tasks.append(
                                asyncio.create_task(
                                    self.notify_teapot(account, uid, notes.until_realm_currency_recovery + 60)
                                )
                            )
                except Exception:
                    logging.exception(f"Failure to check resin info for {uid}")

            await gs.close()

        await asyncio.gather(*tasks)

    async def notify_resin(
        self, account: GenshinUser, uid: int, in_seconds: float
    ):
        logging.info(f"Notifying {uid} for resin in {in_seconds:.3f} seconds.")
        await asyncio.sleep(in_seconds)

        for i in range(5):
            gs = account.client
            notes = await gs.get_notes(uid)
            await gs.close()

            if notes.current_resin < notes.max_resin:
                return

            if notes.max_resin > 0:
                break
        else:
            return

        logging.info(f"Sending DM to {account.discord_id}")
        discord_user = await self.bot.fetch_user(account.discord_id)
        channel = await discord_user.create_dm()
        embed = discord.Embed(
            title="Your resin is capped!",
            description=f"UID: {uid}",
            color=0xFF1100,
        )
        embed.set_footer(text="You can turn this notification off via /user settings")
        await channel.send(embed=embed)
        session.merge(
            ScheduledItem(
                id=uid,
                type=self.RESIN_KEY,
                scheduled_at=datetime.utcnow(),
                done=True,
            )
        )
        session.commit()

    async def notify_teapot(
        self, account: GenshinUser, uid: int, in_seconds: float
    ):
        logging.info(f"Notifying {uid} for teapot in {in_seconds:.3f} seconds.")
        await asyncio.sleep(in_seconds)

        for i in range(5):
            gs = account.client
            notes = await gs.get_notes(uid)
            await gs.close()

            if notes.current_realm_currency < notes.max_realm_currency:
                return

            if notes.max_realm_currency > 0:
                break
        else:
            return

        logging.info(f"Sending DM to {account.discord_id}")
        discord_user = await self.bot.fetch_user(account.discord_id)
        channel = await discord_user.create_dm()
        embed = discord.Embed(
            title="Your teapot currency is capped!",
            description=f"UID: {uid}",
            color=0xFF1100,
        )
        embed.set_thumbnail(
            url="https://static.wikia.nocookie.net/gensin-impact/images/5/5a/Item_Serenitea_Pot.png")
        embed.set_footer(text="You can turn this notification off via /user settings")
        await channel.send(embed=embed)
        session.merge(
            ScheduledItem(
                id=uid,
                type=self.TEAPOT_KEY,
                scheduled_at=datetime.utcnow(),
                done=True,
            )
        )
        session.commit()
