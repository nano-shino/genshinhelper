from datetime import datetime

import discord

from common.constants import Time
from common.db import session
from datamodels.scheduling import ScheduledItem, ItemType


class ReminderButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        self.view.remove_item(self)

        discord_id, uid = map(int, interaction.data["custom_id"].split("-"))
        ready_at = datetime.now() + Time.PARAMETRIC_TRANSFORMER_COOLDOWN

        try:
            reminder = session.get(
                ScheduledItem, (uid, ItemType.PARAMETRIC_TRANSFORMER)
            )

            # If the user clicks the button after the reminder is already renewed by automatic parametric detection
            # then we don't schedule the next one.
            if reminder and not reminder.done:
                # This shouldn't happen unless the bot wasn't able to replace this view
                return

            reminder.context = None
            reminder.scheduled_at = ready_at
            reminder.done = False
            session.merge(reminder)
            session.commit()

            await interaction.response.edit_message(
                embed=discord.Embed(
                    description=f"Your next reminder for {uid} will be in 7 days from now: <t:{int(ready_at.timestamp())}>"
                ),
                view=self.view,
            )
        finally:
            self.view.stop()


class ReminderView(discord.ui.View):
    def __init__(self, discord_id: int, uid: int):
        super().__init__(timeout=None)
        custom_id = f"{discord_id}-{uid}"
        self.add_item(
            ReminderButton(
                label="Set next reminder",
                custom_id=custom_id,
                style=discord.ButtonStyle.primary,
            )
        )
