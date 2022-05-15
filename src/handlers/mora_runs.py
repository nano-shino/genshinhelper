import csv
import dataclasses
import io
import math
from collections import defaultdict
from typing import List

import discord
import genshin as genshin
from PIL import Image, ImageDraw
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
MAX_BREAK_TIME = 60 * 2
LOADING_EMBED = discord.Embed(description=Emoji.LOADING + " loading diary data...")


@dataclasses.dataclass
class EliteRunSummary:
    start_ts: int  # Start timestamp
    end_ts: int
    mora: int
    elites_200: int
    elites_400: int
    elites_600: int
    graph: io.BytesIO

    # derived attributes
    @property
    def duration(self) -> int:
        # in seconds
        return self.end_ts - self.start_ts

    @property
    def rate(self) -> float:
        # mora/min
        return self.mora / (self.duration / 60)


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

        async for embeds, files in view.update_view():
            await ctx.edit(embeds=embeds, files=files, attachments=[])


class DayView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext, accounts: List[GenshinUser]):
        super().__init__()
        self.ctx = ctx
        self.delta = 0
        self.graph_delta = 0
        self.accounts = accounts
        self.logs = {}

    @discord.ui.button(label="Previous day", style=discord.ButtonStyle.blurple)
    async def previous(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self.valid(interaction):
            return

        self.delta -= 1
        self.graph_delta = 0
        self.next.disabled = False

        await interaction.response.edit_message(embeds=[LOADING_EMBED], view=self, attachments=[])
        msg = await interaction.original_message()
        async for embeds, files in self.update_view():
            await msg.edit(embeds=embeds, files=files, attachments=[], view=self)

    @discord.ui.button(label="Next day", style=discord.ButtonStyle.blurple, disabled=True)
    async def next(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if not await self.valid(interaction):
            return

        self.delta += 1
        self.graph_delta = 0
        if self.delta == 0:
            button.disabled = True

        await interaction.response.edit_message(embeds=[LOADING_EMBED], view=self, attachments=[])
        msg = await interaction.original_message()
        async for embeds, files in self.update_view():
            await msg.edit(embeds=embeds, files=files, attachments=[])

    @discord.ui.button(label="Show full logs", style=discord.ButtonStyle.green, emoji="📑")
    async def show_full(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if not await self.valid(interaction):
            return

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

    @discord.ui.button(label="<", style=discord.ButtonStyle.gray)
    async def graph_prev(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if not await self.valid(interaction):
            return

        await interaction.response.defer()
        self.graph_delta -= 1

        msg = await interaction.original_message()
        async for embeds, files in self.update_view():
            await msg.edit(embeds=embeds, files=files, attachments=[])

    @discord.ui.button(label=">", style=discord.ButtonStyle.gray)
    async def graph_next(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if not await self.valid(interaction):
            return

        await interaction.response.defer()
        self.graph_delta += 1

        msg = await interaction.original_message()
        async for embeds, files in self.update_view():
            await msg.edit(embeds=embeds, files=files, attachments=[])

    async def valid(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.message.interaction.user.id:
            await interaction.response.send_message(
                f"{interaction.user.mention} tried to click a button", delete_after=5)
            return False
        return True

    async def on_timeout(self) -> None:
        message = await self.ctx.interaction.original_message()
        await message.edit(view=None)

    async def update_view(self):
        success = False
        embeds = []
        files = []
        self.logs = {}

        for account in self.accounts:
            gs = account.client

            for uid in account.genshin_uids:
                server = ServerEnum.from_uid(uid)
                daily_logs = await self.get_mora_data(gs, uid)
                date_str = (server.last_daily_reset + relativedelta(days=self.delta)).strftime('%m-%d-%y')
                self.logs[uid] = {date_str: daily_logs}
                elite_runs = self.analyze_mora_data(daily_logs)

                if not elite_runs:
                    break

                runs = [
                    f"{run.duration / 60:.1f} min · "
                    f"{run.mora} mora · "
                    f"{run.rate:.0f} mora/min\n"
                    f"↳ started at <t:{run.start_ts}:t> · "
                    f"`{run.elites_200}/{run.elites_400}/{run.elites_600}` 200/400/600 elites"
                    for run in elite_runs
                ]

                if server.current_time.timestamp() - elite_runs[-1].end_ts < 5400:
                    runs += [":warning: Last run may be incomplete. Try again later."]

                embed = discord.Embed(
                    title=f":dollar: Elite runs on {date_str}",
                    description="\n".join(runs),
                )
                elite_graph_idx = (self.graph_delta - 1) % len(elite_runs)
                embed.set_footer(
                    text=f"Graph: "
                         f"Each bar shows the total mora earned in 1 minute. "
                         f"The x labels are the 600-mora elites numbered chronologically. "
                         f"A dip may indicate a problem with that elite leg OR the ones next to it "
                         f"as this is not an exact science."
                )
                files.append(
                    discord.File(elite_runs[elite_graph_idx].graph, filename="run_graph.png"))
                embed.set_image(url="attachment://run_graph.png")
                embeds.append(embed)

                yield embeds, files
                success = True

        if not success:
            yield [discord.Embed(description="No elite run found")], []

    async def get_mora_data(self, client: genshin.Client, uid: int) -> List[DiaryAction]:
        server = ServerEnum.from_uid(uid)

        diary = travelers_diary.TravelersDiary(client, uid)
        daily_logs = await diary.fetch_logs(
            DiaryType.MORA,
            server.last_daily_reset + relativedelta(days=self.delta),
            server.last_daily_reset + relativedelta(days=self.delta + 1)
        )

        return daily_logs

    def analyze_mora_data(self, daily_logs: List[DiaryAction]) -> List[EliteRunSummary]:
        groups: List[List[DiaryAction]] = []

        # Find clusters (one continuous stream of mora without gaps longer than a given MAX_BREAK_TIME)
        for action in daily_logs:
            if action.action != MoraAction.KILLING_MONSTER:
                continue
            if not groups:
                groups.append([])
            if groups[-1] and action.timestamp - groups[-1][-1].timestamp >= MAX_BREAK_TIME:
                groups.append([])
            groups[-1].append(action)

        # Filter out non-elites run
        elite_runs = []
        for group in groups:
            elite_count = sum(1 for action in group if action.amount in [600])
            run = EliteRunSummary(
                start_ts=group[0].timestamp,
                end_ts=group[-1].timestamp,
                mora=sum(action.amount for action in group),
                elites_200=sum(1 for a in group if a.amount == 200),
                elites_400=sum(1 for a in group if a.amount == 400),
                elites_600=sum(1 for a in group if a.amount == 600),
                graph=self.graph(group)
            )
            # Filter out runs that are too short (less than 3 minutes)
            if run.duration < 3 * 60:
                continue

            # Filter out runs that have very low rate (unlikely to be an elite run)
            if run.rate < 600:
                continue

            elite_runs.append(run)

        return elite_runs

    def graph(self, run: List[DiaryAction], bar_width: int = 14):
        LEFT_PADDING = 100
        BAR_MAX_HEIGHT = 150
        BAR_RATIO = 20  # mora = ratio * bar_height, so a bar with 100 pixels means ratio * 100 mora.

        start_ts = run[0].timestamp
        end_ts = run[-1].timestamp
        duration = end_ts - start_ts
        number_of_bars = int(math.ceil(duration / 60))
        im = Image.new(mode="RGBA", size=(LEFT_PADDING + number_of_bars * bar_width, BAR_MAX_HEIGHT + 100))
        draw = ImageDraw.Draw(im)
        bars = defaultdict(int)
        labels = defaultdict(list)

        # Number the elites and store based on minute timestamp
        idx_600 = 1
        for entry in run:
            idx = (entry.timestamp - start_ts) // 60
            bars[idx] += entry.amount
            if entry.amount == 600:
                labels[idx].append(str(idx_600))
                idx_600 += 1

        # Draw green bars and numbered labels
        for idx in range(0, number_of_bars):
            draw.rectangle(
                (
                    (LEFT_PADDING + idx * bar_width + 1, BAR_MAX_HEIGHT - bars[idx] / BAR_RATIO),
                    (LEFT_PADDING + (idx + 1) * bar_width - 1, BAR_MAX_HEIGHT)
                ),
                fill="#a0ff3350",
            )
            line = 0
            for l in labels[idx]:
                w, h = draw.textsize(l)
                draw.text((LEFT_PADDING + idx * bar_width + (bar_width - w) / 2 + 1, BAR_MAX_HEIGHT + 10 + line), l)
                line += h + 5

        # Draw horizontal lines
        for y, label in [(2, "2000"), (1, "1000"), (0, "0")]:
            line_y = BAR_MAX_HEIGHT - 1000 // BAR_RATIO * y
            draw.line((LEFT_PADDING, line_y, im.width, line_y), fill="#ffffffb0")
            w, h = draw.textsize(label)
            draw.text((LEFT_PADDING - w - 5, line_y - h / 2), label)

            # Draw dashed lines +1/2 the height
            for x in range(LEFT_PADDING, im.width, 8):
                draw.line([(x, line_y - 500 // BAR_RATIO), (x + 2, line_y - 500 // BAR_RATIO)], fill="#ffffffa0")

        # Crop and save
        bbox = im.getbbox()
        im = im.crop(bbox)
        file = io.BytesIO()
        im.save(file, "PNG")
        file.seek(0)
        return file
