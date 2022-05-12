import csv
import io
import math
from typing import List

import discord
import genshin as genshin
from dateutil.relativedelta import relativedelta
from discord import ApplicationContext
from discord.ext import commands
from sqlalchemy import select

from common import guild_level
from common.constants import Emoji
from common.db import session
from common.genshin_server import ServerEnum
from datamodels.diary_action import DiaryType, MoraAction, DiaryAction
from datamodels.genshin_user import GenshinUser
from interfaces import travelers_diary

MIN_MORA_RUN_THRESHOLD = 2000
MAX_BREAK_TIME = 60 * 3
LOADING_EMBED = discord.Embed(description=Emoji.LOADING + " loading live data...")


class MoraRunHandler(commands.Cog):
    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @commands.slash_command(
        description="Shows info about your elite runs",
        guild_ids=guild_level.get_guild_ids(3),
    )
    async def elites(
        self,
        ctx: ApplicationContext,
    ):
        await ctx.defer()

        accounts = (
            session.execute(
                select(GenshinUser).where(GenshinUser.discord_id == ctx.author.id)
            )
            .scalars()
            .all()
        )

        if not accounts:
            await ctx.send_followup(
                "You don't have any registered accounts with this bot."
            )
            return

        view = DayView(ctx, accounts)

        await ctx.send_followup(embed=LOADING_EMBED, view=view)

        async for embeds in view.update_view():
            await ctx.edit(embeds=embeds)


class DayView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext, accounts: List[GenshinUser]):
        super().__init__()
        self.ctx = ctx
        self.delta = 0
        self.accounts = accounts
        self.logs = {}

    @discord.ui.button(label="Previous day", style=discord.ButtonStyle.blurple)
    async def previous(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(embeds=[LOADING_EMBED], view=self)
        self.delta -= 1
        self.next.disabled = False
        msg = await interaction.original_message()
        async for embeds in self.update_view():
            await msg.edit(embeds=embeds, view=self)

    @discord.ui.button(label="Next day", style=discord.ButtonStyle.blurple, disabled=True)
    async def next(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.edit_message(embeds=[LOADING_EMBED], view=self)
        self.delta += 1
        if self.delta == 0:
            button.disabled = True
        msg = await interaction.original_message()
        async for embeds in self.update_view():
            await msg.edit(embeds=embeds, view=self)

    @discord.ui.button(label="Show full logs", style=discord.ButtonStyle.green, emoji="📑")
    async def show_full(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        files = []

        for uid in self.logs:
            for date_str in self.logs[uid]:
                with io.StringIO() as file:
                    dict_writer = csv.writer(file)
                    dict_writer.writerow(['server_time', 'action_id', 'action', 'amount'])
                    for entry in self.logs[uid][date_str]:
                        dict_writer.writerow([
                            entry.time.strftime("%b %-d %I:%M:%S %p"),
                            entry.action_id,
                            entry.action,
                            entry.amount])

                    file.seek(0)
                    files.append(discord.File(
                        file,
                        filename=f"mora-logs-{str(uid)[-3:]}-{date_str}.csv",
                    ))

        if not files:
            await interaction.response.defer()

        await interaction.response.send_message(files=files)

    async def on_timeout(self) -> None:
        message = await self.ctx.interaction.original_message()
        await message.edit(view=None)

    async def update_view(self):
        success = False
        embeds = []
        self.logs = {}

        for account in self.accounts:
            gs = account.client

            for uid in account.genshin_uids:
                server = ServerEnum.from_uid(uid)
                daily_logs = await self.get_mora_data(gs, uid)
                date_str = (server.last_daily_reset + relativedelta(days=self.delta)).strftime('%m-%d-%y')
                self.logs[uid] = {date_str: daily_logs}
                elite_data = self.analyze_mora_data(daily_logs)
                runs = [
                    f"{math.ceil(time / 60):.0f} min | "
                    f"{mora} mora | "
                    f"{mora / time * 60:.0f} mora/min\n"
                    f"(started at <t:{ts}:t>)"
                    for time, mora, ts in elite_data
                ]

                if not runs:
                    break

                embed = discord.Embed(
                    title=f"Elite runs on {date_str}",
                    description="\n".join(runs),
                )
                embed.set_footer(
                    text=f"UID-{str(uid)[-3:]} | Current server time: {server.current_time.strftime('%b %e %I:%M %p')}"
                )
                embeds.append(embed)

                yield embeds
                success = True

        if not success:
            yield [discord.Embed(description="No elite run found")]

    async def get_mora_data(self, client: genshin.Client, uid: int) -> List[DiaryAction]:
        server = ServerEnum.from_uid(uid)

        diary = travelers_diary.TravelersDiary(client, uid)
        daily_logs = await diary.fetch_logs(
            DiaryType.MORA,
            server.last_daily_reset + relativedelta(days=self.delta),
            server.last_daily_reset + relativedelta(days=self.delta + 1)
        )

        return daily_logs

    def analyze_mora_data(self, daily_logs: List[DiaryAction]):
        timestamps = []
        mora = []
        for action in daily_logs:
            if action.action == MoraAction.KILLING_MONSTER:
                timestamps.append(action.timestamp)
                mora.append(action.amount)

        # Aggregate per minute
        new_values = []
        for x, y in zip(timestamps, mora):
            if new_values:
                for x1 in range(int(new_values[-1][0]) + 60, int(x // 60) * 60, 60):
                    new_values.append([x1, 0])
            if new_values and new_values[-1][0] >= x - 60:
                new_values[-1][1] += y
            else:
                new_values.append([x // 60 * 60, y])

        # Find clusters (aka. one mora run)
        groups = []
        for x, y in zip(timestamps, mora):
            if groups and groups[-1][1] >= x - MAX_BREAK_TIME:
                groups[-1][1] = x
                groups[-1][2] += y
            elif y in [200, 600]:
                groups.append([x, x, y])

        return_data = []
        for group in groups:
            if group[2] >= MIN_MORA_RUN_THRESHOLD:
                return_data.append((group[1] - group[0], group[2], group[0]))

        return return_data