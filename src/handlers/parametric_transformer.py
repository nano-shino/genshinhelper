import asyncio
import random
from typing import List

import discord
import pytz
from dateutil.relativedelta import relativedelta
from discord.ext import commands, tasks
from sqlalchemy import select

from common.constants import Time
from common.db import session
from common.genshin_server import ServerEnum
from common.logging import logger
from datamodels.account_settings import Preferences
from datamodels.diary_action import DiaryType, MoraActionId, MoraAction
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem, ItemType
from interfaces import travelers_diary
from views.reminder import ReminderView


class ParametricTransformer(commands.Cog):
    SCANNER_BACKTRACK_HOURS = 6

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            for scheduled_task in session.execute(select(ScheduledItem).where(ScheduledItem.done)).scalars():
                if not scheduled_task.context:
                    continue

                discord_id = scheduled_task.context.get('discord_id')
                message_id = scheduled_task.context.get('message_id')

                if discord_id and message_id:
                    self.bot.add_view(
                        ReminderView(discord_id, scheduled_task.id),
                        message_id=scheduled_task.context.get('message_id')
                    )

            await asyncio.sleep(
                random.randint(3 * 60, 5 * 60))  # sleep randomly so everything doesn't start up at once.
            self.scanner_job.start()
            self.start_up = True

    @tasks.loop(hours=SCANNER_BACKTRACK_HOURS)
    async def scanner_job(self):
        all_accounts: List[GenshinUser] = session.execute(select(GenshinUser)).scalars()
        for account in all_accounts:
            await scan_account(self.bot, account, self.SCANNER_BACKTRACK_HOURS + 1)


async def scan_account(bot: discord.Bot, account: GenshinUser, scan_amount_hrs: int):
    discord_id = account.discord_id

    if not account.settings[Preferences.PARAMETRIC_TRANSFORMER]:
        return

    for uid in account.genshin_uids:
        reminder = session.get(ScheduledItem, (uid, ItemType.PARAMETRIC_TRANSFORMER))

        # A reminder is already scheduled. We should let it finish first.
        if reminder and not reminder.done:
            continue

        logger.info(f"Scanning diary logs for parametric transformer usage uid={uid}")

        server = ServerEnum.from_uid(uid)

        client = account.client
        diary = travelers_diary.TravelersDiary(client, uid)

        start_time = server.current_time - relativedelta(hours=scan_amount_hrs)
        logs = await diary.fetch_logs(
            diary_type=DiaryType.MORA, start_time=start_time
        )
        await client.close()

        for entry in logs:
            if (entry.action_id == MoraActionId.PARAMETRIC_TRANSFORMER and
                    entry.action == MoraAction.EVENT and
                    entry.amount % 20000 == 0):

                discord_user = await bot.fetch_user(discord_id)
                channel = await discord_user.create_dm()
                ready_at = entry.time + Time.PARAMETRIC_TRANSFORMER_COOLDOWN
                detect_message = f"Detected Parametric Transformer usage <t:{int(entry.timestamp)}:R> on " \
                                 f"`UID {uid}`.\n" \
                                 f"Scheduling next reminder at <t:{int(ready_at.timestamp())}>"
                logger.info(detect_message)

                if reminder and reminder.context and reminder.context.get('message_id'):
                    message = await channel.fetch_message(reminder.context.get('message_id'))
                    await message.edit(content=detect_message, view=None)
                else:
                    await channel.send(detect_message)

                reminder = ScheduledItem(
                    id=uid,
                    type=ItemType.PARAMETRIC_TRANSFORMER,
                    scheduled_at=ready_at.astimezone(tz=pytz.UTC),
                    done=False
                )
                session.merge(reminder)
                session.commit()
