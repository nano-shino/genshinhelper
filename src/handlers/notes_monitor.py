import asyncio
import logging
from datetime import datetime

import discord
import genshin.models
import pytz
from discord.ext import tasks, commands
from sqlalchemy import select

from common.constants import Preferences
from common.db import session
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem, ItemType
from utils.game_notes import get_notes


class RealTimeNotesMonitor(commands.Cog):
    CHECK_INTERVAL = 60 * 60 * 3  # Frequency of querying notes

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            # await asyncio.sleep(
            #     random.randint(0, 60)
            # )  # sleep randomly so everything doesn't start up at once.
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
            logging.info("Finished periodic resin check")
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

            gs = account.client

            for uid in account.genshin_uids:
                try:
                    raw_notes = await get_notes(gs, uid)
                    notes: genshin.models.Notes = genshin.models.Notes(**raw_notes)

                    if resin_reminder and notes.max_resin > 0:
                        reminder = session.get(ScheduledItem, (uid, ItemType.RESIN_CAP))

                        if reminder and notes.remaining_resin_recovery_time > 0:
                            session.delete(reminder)
                            session.commit()
                            reminder = None

                        if not reminder and notes.remaining_resin_recovery_time < self.CHECK_INTERVAL:
                            tasks.append(
                                asyncio.create_task(
                                    self.notify_resin(account, uid, notes.remaining_resin_recovery_time + 60)
                                )
                            )

                    if teapot_reminder and notes.max_realm_currency > 0:
                        reminder = session.get(ScheduledItem, (uid, ItemType.TEAPOT_CAP))

                        if reminder and notes.remaining_realm_currency_recovery_time > 0:
                            session.delete(reminder)
                            session.commit()
                            reminder = None

                        # "greater than 0" to prevent a bug where current coins = max coins
                        if not reminder and 0 < notes.remaining_realm_currency_recovery_time < self.CHECK_INTERVAL:
                            tasks.append(
                                asyncio.create_task(
                                    self.notify_teapot(account, uid, notes.remaining_realm_currency_recovery_time + 60)
                                )
                            )

                    if raw_notes["transformer"] and not raw_notes["transformer"]["recovery_time"]["reached"]:
                        # This means that the transformer is currently on cooldown
                        reminder = ScheduledItem(
                            id=uid,
                            type=ItemType.PARAMETRIC_TRANSFORMER,
                            scheduled_at=notes.transformer_recovery_time.astimezone(tz=pytz.UTC),
                            done=False,
                        )
                        session.merge(reminder)
                        session.commit()

                except Exception:
                    logging.exception(f"Failure to check resin info for {uid}")

        await asyncio.gather(*tasks)

    async def notify_resin(
        self, account: GenshinUser, uid: int, in_seconds: float
    ):
        logging.info(f"Notifying {uid} for resin in {in_seconds:.3f} seconds.")
        await asyncio.sleep(in_seconds)

        for i in range(5):
            gs = account.client
            notes = await gs.get_notes(uid)

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
                type=ItemType.RESIN_CAP,
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
                type=ItemType.TEAPOT_CAP,
                scheduled_at=datetime.utcnow(),
                done=True,
            )
        )
        session.commit()
