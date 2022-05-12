import csv
import io
import math
from typing import List

import discord
import genshin as genshin
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

        embed = discord.Embed(description=Emoji.LOADING + " loading live data...")
        await ctx.send_followup(embed=embed)

        success = False
        embeds = []
        files = []
        for account in accounts:
            gs = account.client

            for uid in account.genshin_uids:
                server = ServerEnum.from_uid(uid)
                daily_logs = await self.get_mora_data(gs, uid)
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
                    title="Elite runs from last server reset",
                    description="\n".join(runs),
                )
                embed.set_footer(
                    text=f"UID-{str(uid)[-3:]} | Current server time: {server.current_time.strftime('%b %e %I:%M %p')}"
                )
                embeds.append(embed)

                with io.StringIO() as file:
                    dict_writer = csv.writer(file)
                    dict_writer.writerow(['action_id', 'action', 'timestamp', 'amount'])
                    for entry in daily_logs:
                        dict_writer.writerow([
                            entry.action_id,
                            entry.action,
                            entry.time.strftime("%b %e %I:%M:%S %p"),
                            entry.amount])

                    file.seek(0)
                    date_str = server.last_daily_reset.strftime('%m-%d-%y')
                    files.append(discord.File(
                        file,
                        filename=f"mora-logs-{uid}-{date_str}.csv",
                    ))

                await ctx.edit(embeds=embeds, files=files)
                success = True

        if not success:
            await ctx.edit(embed=discord.Embed(description="No data found"))

    async def get_mora_data(self, client: genshin.GenshinClient, uid: int) -> List[DiaryAction]:
        server = ServerEnum.from_uid(uid)

        diary = travelers_diary.TravelersDiary(client, uid)
        daily_logs = await diary.fetch_logs(DiaryType.MORA, server.last_daily_reset)

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
