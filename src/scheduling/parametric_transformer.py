import discord

from common.db import session
from datamodels.account_settings import Preferences
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem
from datamodels.uid_mapping import UidMapping
from resources import RESOURCE_PATH
from views.reminder import ReminderView


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
    view = ReminderView(discord_id=account.discord_id, uid=uid)
    message = await channel.send(
        f"Your parametric transformer is ready for use `UID {uid}`\n"
        f"Click Set next reminder after you have used the transformer as it will "
        f"immediately schedule the next one from the time you click.",
        view=view,
        file=discord.File(str(RESOURCE_PATH / "transformer_guide.png")),
    )

    scheduled_task.context = {
        "discord_id": account.discord_id,
        "message_id": message.id,
    }
    session.merge(scheduled_task)
    session.commit()
