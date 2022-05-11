import datetime

import dateparser
import discord
import pytz
from discord import SlashCommandGroup, Option
from discord.ext import commands
from discord.utils import AutocompleteContext, V

from common import guild_level, authentication
from common.autocomplete import get_uid_suggestions
from common.db import session
from datamodels.scheduling import ScheduledItem
from scheduling.types import ScheduleType


async def dateparsing_autocomplete_callback(ctx: AutocompleteContext) -> V:
    try:
        dtime = dateparser.parse(ctx.value).astimezone(tz=pytz.UTC)
    except Exception:
        return []

    return [f"{dtime.strftime('%Y-%m-%d %H:%M:%S %Z')}"]


class RemindHandler(commands.Cog):
    REMINDER_TRANSLATE = {
        "parametric": ScheduleType.PARAMETRIC_TRANSFORMER,
    }
    REMINDER_OPTIONS = list(REMINDER_TRANSLATE.keys())

    remind = SlashCommandGroup(
        "remind", "Remind you to do things", guild_ids=guild_level.get_guild_ids(level=3)
    )

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @remind.command(
        description="Set a reminder",
        guild_ids=guild_level.get_guild_ids(level=3),
    )
    async def set(
            self,
            ctx: discord.ApplicationContext,
            type: Option(str, "Type of the reminder", choices=REMINDER_OPTIONS),
            _uid: Option(str, "Genshin UID", name="uid", autocomplete=get_uid_suggestions),
            when: Option(
                str,
                'When to remind. Flexible format: "in 2 hours", "2022-02-01T20:49:25+05:00"',
                autocomplete=dateparsing_autocomplete_callback),
    ):
        uid = int(_uid)

        if not authentication.own_uid(ctx.author.id, uid):
            await ctx.respond("This UID is not linked to your Discord account.")
            return

        try:
            remind_at = dateparser.parse(when).astimezone(tz=pytz.UTC)
        except Exception:
            await ctx.respond("Unable to parse time input")
            return

        if remind_at < datetime.datetime.now(tz=pytz.UTC):
            await ctx.respond("Time is in the past")
            return

        try:
            remind_type = self.REMINDER_TRANSLATE[type]
        except Exception:
            await ctx.respond("Reminder type is not valid")
            return

        item = ScheduledItem(
            id=uid,
            type=remind_type,
            scheduled_at=remind_at,
            done=False,
            context=None
        )

        view = ReminderConfirmView(ctx)
        ts = int(remind_at.timestamp())

        await ctx.respond(
            embed=discord.Embed(
                description=f"Reminder to be set at <t:{ts}> (<t:{ts}:R>)"
            ),
            view=view,
        )

        await view.wait()

        if view.value is None:
            await ctx.edit(
                embed=discord.Embed(description=f"Action timed out"), view=None
            )
        elif view.value:
            session.merge(item)
            session.commit()
            await ctx.edit(
                embed=discord.Embed(description=f"Reminder set"), view=None
            )
        else:
            await ctx.edit(
                embed=discord.Embed(description=f"Reminder cancelled"), view=None
            )


class ReminderConfirmView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext):
        super().__init__()
        self.ctx = ctx
        self.value = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def confirm(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.value = True
        self.stop()

    async def on_timeout(self) -> None:
        """Disables all buttons when the view times out."""
        for item in self.children:
            item.disabled = True
        message = await self.ctx.interaction.original_message()
        await message.edit(view=self)
