import discord

from common.db import session
from common.constants import Preferences
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem
from datamodels.uid_mapping import UidMapping
from resources import RESOURCE_PATH


async def task_handler(bot: discord.Bot, scheduled_task: ScheduledItem):
    genshin_uid = scheduled_task.id
    mapping = session.get(UidMapping, (genshin_uid,))

    if mapping:
        mihoyo_id = mapping.mihoyo_id
        account = session.get(GenshinUser, (mihoyo_id,))
        await send_reminder(bot, account, scheduled_task)


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
