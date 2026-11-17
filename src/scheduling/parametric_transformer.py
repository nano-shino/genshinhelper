import asyncio

import discord
import genshin

from common.db import session
from common.constants import Preferences
from common.logging import logger
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem
from datamodels.uid_mapping import UidMapping
from resources import RESOURCE_PATH
from utils.game_notes import get_notes


async def task_handler(bot: discord.Bot, scheduled_task: ScheduledItem):
    genshin_uid = scheduled_task.id
    mapping = session.get(UidMapping, (genshin_uid,))

    if mapping:
        mihoyo_id = mapping.mihoyo_id
        account = session.get(GenshinUser, (mihoyo_id,))

        # Token was already removed (e.g. expired), nothing we can check anymore
        if not account or not account.hoyolab_token:
            return

        for _ in range(12):
            try:
                raw_notes = await get_notes(account.client, genshin_uid)
            except genshin.errors.InvalidCookies:
                account.hoyolab_token = None
                session.merge(account)
                session.commit()
                await notify_expired_token(bot, account)
                return

            if raw_notes["transformer"] and raw_notes["transformer"]["recovery_time"]["reached"]:
                await send_reminder(bot, account, scheduled_task)
                break

            logger.info(f"Transformer for {genshin_uid} is not ready yet. Checking again soon.")
            await asyncio.sleep(5 * 60)


async def send_reminder(
    bot: discord.Bot, account: GenshinUser, scheduled_task: ScheduledItem
):
    if not account.settings[Preferences.PARAMETRIC_TRANSFORMER]:
        return

    uid = scheduled_task.id
    discord_user = await bot.fetch_user(account.discord_id)
    channel = await discord_user.create_dm()

    await channel.send(
        f"Your parametric transformer is now ready. `UID {uid}`\n",
        file=discord.File(str(RESOURCE_PATH / "transformer_guide.png")),
    )


async def notify_expired_token(bot: discord.Bot, account: GenshinUser):
    discord_user = await bot.fetch_user(account.discord_id)
    channel = await discord_user.create_dm()

    await channel.send(
        embed=discord.Embed(
            title=":warning: Account Access Failure",
            description=f"Your ltoken has expired for Hoyolab ID {account.mihoyo_id}.\n"
                        f"This may be because you have changed your password recently.\n"
                        f"Please register again if you want to continue using the bot."
        )
    )
