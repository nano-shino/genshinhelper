import asyncio
from datetime import datetime
from typing import Iterable

import discord
from dateutil.relativedelta import relativedelta
from discord.ext import commands, tasks
from sqlalchemy import select

from common.db import session
from common.logging import logger
from datamodels.scheduling import ScheduledItem
from scheduling import parametric_transformer
from scheduling.types import ScheduleType


class Dispatcher(commands.Cog):
    task_interval = 60
    supported_handlers = {
        ScheduleType.PARAMETRIC_TRANSFORMER: parametric_transformer.task_handler,
    }

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            self.job.start()
            self.start_up = True

    @tasks.loop(seconds=task_interval, reconnect=False)
    async def job(self):
        # Get all scheduled tasks within the interval
        scheduled_tasks: Iterable[ScheduledItem] = (
            session.execute(
                select(ScheduledItem)
                .where(
                    ScheduledItem.type.in_(self.supported_handlers),
                    ScheduledItem.scheduled_at
                    < datetime.utcnow() + relativedelta(seconds=self.task_interval),
                    ~ScheduledItem.done,
                )
                .order_by(ScheduledItem.scheduled_at.asc())
            )
            .scalars()
            .all()
        )

        # Sleep until the earliest task is ready
        for task in scheduled_tasks:
            scheduled_at = task.scheduled_at
            wait_time = max((scheduled_at - datetime.utcnow()).total_seconds(), 0)
            await asyncio.sleep(wait_time)

            try:
                logger.info(f"Dispatching task: {task.id}, {task.type}")
                await self.supported_handlers[task.type](self.bot, task)
                task.done = True
                session.merge(task)
                session.commit()
            except Exception:
                logger.exception("Task failed to dispatch")
                pass
