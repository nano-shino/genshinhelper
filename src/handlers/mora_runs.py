import math

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
from datamodels.diary_action import DiaryType, MoraAction
from datamodels.genshin_user import GenshinUser
from interfaces import travelers_diary

MIN_MORA_RUN_THRESHOLD = 5000


class MoraRunHandler(commands.Cog):

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @commands.slash_command(
        description="Get info about your elite runs",
        guild_ids=guild_level.get_guild_ids(3),
    )
    async def elites(
            self,
            ctx: ApplicationContext,
    ):
        await ctx.defer()

        accounts = session.execute(select(GenshinUser).where(GenshinUser.discord_id == ctx.author.id)).scalars().all()

        if not accounts:
            await ctx.send_followup("You don't have any registered accounts with this bot.")
            return

        embed = discord.Embed(description=Emoji.LOADING + " loading live data...")
        await ctx.send_followup(embed=embed)

        embeds = []
        for account in accounts:
            gs: genshin.GenshinClient = account.client

            for uid in account.genshin_uids:
                data = await self.get_mora_run_data(gs, uid)
                runs = [f"{math.ceil(time / 60):.0f} min | "
                        f"{mora} mora | "
                        f"{mora / time * 60:.0f} mora/min\n"
                        f"(started at <t:{ts}:t>)" for time, mora, ts in data]

                embed = discord.Embed(
                    title="Elite runs from last server reset",
                    description="\n".join(runs) or "No elite runs found")
                embeds.append(embed)

                await ctx.edit(embeds=embeds)

            await gs.session.close()

    async def get_mora_run_data(self, client: genshin.GenshinClient, uid: int):
        server = ServerEnum.from_uid(uid)

        diary = travelers_diary.TravelersDiary(client, uid)
        daily_logs = await diary.fetch_logs(DiaryType.MORA, server.last_daily_reset)

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
            if groups and groups[-1][1] >= x - 120:
                groups[-1][1] = x
                groups[-1][2] += y
            elif y == 600:
                groups.append([x, x, y])

        return_data = []
        for group in groups:
            if group[2] >= MIN_MORA_RUN_THRESHOLD:
                return_data.append((group[1] - group[0], group[2], group[0]))

        return return_data
