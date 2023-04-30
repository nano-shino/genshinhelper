import asyncio
from datetime import datetime
from typing import List

import discord
import genshin.models
import pytz
from discord.ext import tasks, commands
from sqlalchemy import select

from common.constants import Preferences
from common.db import session
from common.logging import logger
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem, ItemType
from utils.game_notes import get_notes


# This is the duration in seconds that the "real-time" notes lag behind actual game data.
# I haven't measured it precisely, but it should be less than 60 seconds so this gives some buffer for error.
REAL_TIME_NOTES_LAG = 60


class BaseMonitor:
    def __init__(self, bot: discord.Bot):
        """
        Initialize a monitor, which can handle scheduling and notification for things like resin or transformer.

        :param bot: the discord bot object, needed for sending dm.
        """
        self.bot = bot

    async def should_schedule_notification(self, account: GenshinUser, uid: int) -> bool:
        """
        Implement this to return whether the Discord user wants notification for this uid.
        Should read user_preferences table.
        """
        raise NotImplementedError()

    async def schedule_notification(
            self,
            account: GenshinUser,
            uid: int,
            task_interval: int
    ) -> List[asyncio.Task]:
        """
        Implement this to schedule the notification.
        Must return a list of asyncio tasks or an empty list if none needed.

        :param account: GenshinUser database object.
        :param uid: Genshin UID.
        :param task_interval: Duration in seconds when the next task iteration will happen.
            If something happens beyond this interval, you should let the next task handle it.
        :return: A list of asyncio tasks to be scheduled.
        """
        raise NotImplementedError()

    async def should_notify(self, notes: genshin.models.Notes) -> bool:
        """
        Implement this to return whether we should notify the user based on the notes data.
        Should determine based on whether the item has capped in notes.
        """
        raise NotImplementedError()

    async def create_notification_embed(self, uid: int) -> discord.Embed:
        """
        Implement this to create an embed that will be sent to the Discord user owning the uid.
        The embed should inform that the item has capped.
        """
        raise NotImplementedError()

    async def cleanup(self, uid: int):
        """
        Any cleanup like clearing the reminders out should be done here.
        """
        pass

    async def notify(
            self, account: GenshinUser, uid: int, in_seconds: float
    ):
        """
        Confirm that a notification should happen and send a DM to the user.
        """
        logger.info(f"[{self.__class__.__name__}] Notifying {uid} in {in_seconds:.3f} seconds.")
        await asyncio.sleep(in_seconds)

        raw_notes = await get_notes(account.client, uid)
        notes = genshin.models.Notes(**raw_notes, lang="en-us")

        if not await self.should_notify(notes):
            return

        await self.send_dm(account, uid)
        await self.cleanup(uid)

    async def send_dm(self, account: GenshinUser, uid: int):
        logger.info(f"Sending DM to {account.discord_id}")
        discord_user = await self.bot.fetch_user(account.discord_id)
        channel = await discord_user.create_dm()
        await channel.send(embed=await self.create_notification_embed(uid))


class ResinMonitor(BaseMonitor):
    async def should_schedule_notification(self, account: GenshinUser, uid: int) -> bool:
        return account.settings[Preferences.RESIN_REMINDER]

    async def schedule_notification(
            self,
            account: GenshinUser,
            uid: int,
            task_interval: int
    ) -> List[asyncio.Task]:
        raw_notes = await get_notes(account.client, uid)
        notes: genshin.models.Notes = genshin.models.Notes(**raw_notes, lang="en-us")

        if notes.max_resin > 0:
            reminder = session.get(ScheduledItem, (uid, ItemType.RESIN_CAP))

            if reminder and notes.remaining_resin_recovery_time.total_seconds() > 0:
                session.delete(reminder)
                session.commit()
                reminder = None

            if not reminder and notes.remaining_resin_recovery_time.total_seconds() < task_interval:
                return [
                    asyncio.create_task(
                        self.notify(
                            account,
                            uid,
                            notes.remaining_resin_recovery_time.total_seconds() + REAL_TIME_NOTES_LAG
                        )
                    )
                ]

        return []

    async def should_notify(self, notes) -> bool:
        return notes.current_resin == notes.max_resin > 0

    async def create_notification_embed(self, uid: int) -> discord.Embed:
        embed = discord.Embed(
            title="Your resin is capped!",
            description=f"UID: {uid}",
            color=0xFF1100,
        )
        embed.set_footer(text="You can turn this notification off in /user settings")
        return embed

    async def cleanup(self, uid: int):
        session.merge(
            ScheduledItem(
                id=uid,
                type=ItemType.RESIN_CAP,
                scheduled_at=datetime.utcnow(),
                done=True,
            )
        )
        session.commit()


class ExpeditionMonitor(BaseMonitor):
    async def should_schedule_notification(self, account: GenshinUser, uid: int) -> bool:
        return account.settings[Preferences.EXPEDITION_REMINDER]

    async def schedule_notification(
            self,
            account: GenshinUser,
            uid: int,
            task_interval: int
    ) -> List[asyncio.Task]:
        raw_notes = await get_notes(account.client, uid)
        notes: genshin.models.Notes = genshin.models.Notes(**raw_notes, lang="en-us")

        if notes.expeditions:
            reminder = session.get(ScheduledItem, (uid, ItemType.EXPEDITION_CAP))
            max_remaining_time = max(exp.remaining_time.total_seconds() for exp in notes.expeditions)

            if reminder and max_remaining_time > 0:
                session.delete(reminder)
                session.commit()
                reminder = None

            if not reminder and max_remaining_time < task_interval:
                return [
                    asyncio.create_task(
                        self.notify(account, uid, max_remaining_time + REAL_TIME_NOTES_LAG)
                    )
                ]

        return []

    async def should_notify(self, notes) -> bool:
        if not notes.expeditions:
            return False
        return all(expedition.status == "Finished" for expedition in notes.expeditions)

    async def create_notification_embed(self, uid: int) -> discord.Embed:
        embed = discord.Embed(
            title="Your expeditions are complete!",
            description=f"UID: {uid}",
            color=0xFF1100,
        )
        embed.set_footer(text="You can turn this notification off in /user settings")
        return embed

    async def cleanup(self, uid: int):
        session.merge(
            ScheduledItem(
                id=uid,
                type=ItemType.EXPEDITION_CAP,
                scheduled_at=datetime.utcnow(),
                done=True,
            )
        )
        session.commit()


class TeapotMonitor(BaseMonitor):
    async def should_schedule_notification(self, account: GenshinUser, uid: int) -> bool:
        return account.settings[Preferences.TEAPOT_REMINDER]

    async def schedule_notification(
            self,
            account: GenshinUser,
            uid: int,
            task_interval: int
    ) -> List[asyncio.Task]:
        raw_notes = await get_notes(account.client, uid)
        notes: genshin.models.Notes = genshin.models.Notes(**raw_notes, lang="en-us")

        if notes.max_realm_currency > 0:
            reminder = session.get(ScheduledItem, (uid, ItemType.TEAPOT_CAP))

            if reminder and notes.remaining_realm_currency_recovery_time.total_seconds() > 0:
                session.delete(reminder)
                session.commit()
                reminder = None

            # "greater than 0" to prevent a bug where current coins = max coins
            if not reminder and 0 < notes.remaining_realm_currency_recovery_time.total_seconds() < task_interval:
                return [
                    asyncio.create_task(
                        self.notify(
                            account,
                            uid,
                            notes.remaining_realm_currency_recovery_time.total_seconds() + REAL_TIME_NOTES_LAG)
                    )
                ]

        return []

    async def should_notify(self, notes):
        return notes.current_realm_currency == notes.max_realm_currency > 0

    async def create_notification_embed(self, uid: int) -> discord.Embed:
        embed = discord.Embed(
            title="Your teapot currency is capped!",
            description=f"UID: {uid}",
            color=0xFF1100,
        )
        embed.set_thumbnail(
            url="https://static.wikia.nocookie.net/gensin-impact/images/5/5a/Item_Serenitea_Pot.png")
        embed.set_footer(text="You can turn this notification off in /user settings")
        return embed

    async def cleanup(self, uid: int):
        session.merge(
            ScheduledItem(
                id=uid,
                type=ItemType.TEAPOT_CAP,
                scheduled_at=datetime.utcnow(),
                done=True,
            )
        )
        session.commit()


class TransformerMonitor(BaseMonitor):
    """
    Note that the notification handler for transformer is in the scheduling package.
    Ideally we should be using that package for all scheduling but this works for now.
    """

    async def should_schedule_notification(self, account: GenshinUser, uid: int) -> bool:
        return account.settings[Preferences.PARAMETRIC_TRANSFORMER]

    async def schedule_notification(
            self,
            account: GenshinUser,
            uid: int,
            task_interval: int
    ) -> List[asyncio.Task]:
        raw_notes = await get_notes(account.client, uid)
        notes: genshin.models.Notes = genshin.models.Notes(**raw_notes, lang="en-us")

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

        return []

    async def should_notify(self, notes: genshin.models.Notes) -> bool:
        return False

    async def create_notification_embed(self, uid: int) -> discord.Embed:
        raise RuntimeError("Not expected flow")


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
        logger.info("Begin periodic real-time notes check")

        tasks = []
        for discord_id in session.execute(
                select(GenshinUser.discord_id.distinct())
        ).scalars():
            tasks.append(asyncio.create_task(self.check_accounts(discord_id)))

        try:
            await asyncio.gather(*tasks)
            logger.info("Finished periodic real-time notes check")
        except Exception:
            logger.exception("Failure to check real-time notes")

    async def check_accounts(self, discord_id: int):
        tasks = []
        monitors: List[BaseMonitor] = [
            ResinMonitor(self.bot),
            ExpeditionMonitor(self.bot),
            TeapotMonitor(self.bot),
            TransformerMonitor(self.bot),
        ]

        for account in session.execute(
                select(GenshinUser).where(GenshinUser.discord_id == discord_id)
        ).scalars():
            for uid in account.genshin_uids:
                try:
                    for monitor in monitors:
                        if not await monitor.should_schedule_notification(account, uid):
                            continue

                        new_tasks = await monitor.schedule_notification(account, uid, self.CHECK_INTERVAL)
                        tasks += new_tasks
                except Exception:
                    logger.exception(f"Failure to check {uid}")

        await asyncio.gather(*tasks)
