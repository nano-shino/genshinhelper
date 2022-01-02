from datetime import datetime

import discord
import genshin as genshin
import pytz
from discord import ApplicationContext
from discord.ext import commands
from sqlalchemy import select

from common.constants import Emoji
from common.db import session
from common.genshin_server import ServerEnum
from datamodels.diary_action import DiaryType, MoraAction, MoraActionId
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem, ItemType
from interfaces import travelers_diary


class GameInfoHandler(commands.Cog):

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @commands.slash_command(
        description="Shows your current resin amount"
    )
    async def resin(
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
        success = False
        for account in accounts:
            gs: genshin.GenshinClient = account.client

            for uid in account.genshin_uids:
                embed = discord.Embed()
                embeds.append(embed)

                notes = await gs.get_notes(uid)
                resin_capped = notes.current_resin == notes.max_resin
                exp_completed_at = max(exp.completed_at for exp in notes.expeditions)
                embed.set_footer(text=f"*Daily/weekly data is behind by 1 hour | UID-{uid % 1000}")
                embed.add_field(
                    name=f"<:resin:907486661678624798> {notes.current_resin}/{notes.max_resin}",
                    value=(":warning: capped OMG" if resin_capped
                           else f"capped <t:{int(notes.resin_recovered_at.timestamp())}:R>")
                )
                embed.add_field(
                    name=f"{len(notes.expeditions)}/{notes.max_expeditions} expeditions dispatched",
                    value=(":warning: all done" if exp_completed_at <= datetime.now().astimezone()
                           else f"done <t:{int(exp_completed_at.timestamp())}:R>")
                )
                embed.add_field(
                    name="\u200b",
                    value=f"{Emoji.LOADING} loading non-live data...",
                    inline=False
                )
                await ctx.edit(embeds=embeds)

                diary_data = await self.get_diary_data(gs, uid)
                embed.set_field_at(
                    2,
                    name="\u200b",
                    value="\n".join(f"**{key}:** {val}" for key, val in diary_data.items()),
                    inline=False
                )
                await ctx.edit(embeds=embeds)
                success = True

            await gs.session.close()

        if not success:
            await ctx.edit(embed=discord.Embed(description="No UID found"))

    async def get_diary_data(self, client: genshin.GenshinClient, uid: int):
        server = ServerEnum.from_uid(uid)

        diary = travelers_diary.TravelersDiary(client, uid)
        weekly_logs = await diary.fetch_logs(DiaryType.MORA, server.last_weekly_reset)
        daily_logs = diary.get_logs(DiaryType.MORA, server.last_daily_reset)

        daily_commissions = 0
        daily_commission_bonus = 0
        random_events = 0
        weekly_bosses = 0
        weekly_bounties = 0
        elites = 0

        for action in daily_logs:
            if action.action == MoraAction.DAILY_COMMISSIONS:
                if action.action_id == 26:
                    daily_commission_bonus += 1
                else:
                    daily_commissions += 1
            elif action.action == MoraAction.RANDOM_EVENT:
                random_events += 1
            elif action.action == MoraAction.KILLING_MONSTER and action.amount >= 200:
                elites += 1

        for action in weekly_logs:
            if action.action == MoraAction.KILLING_BOSS and action.amount > 6000:
                # Killing weekly bosses at any AR will give more than 6k (min is 6375, max is 8100)
                weekly_bosses += 1
            if action.action_id == MoraActionId.REPUTATION_BOUNTY:
                weekly_bounties += 1

        bonus = "bonus claimed" if daily_commission_bonus else ":warning: bonus not claimed yet"
        data = {
            'Daily commissions': (":warning: " if daily_commissions < 4 else "") + f'{daily_commissions}/4 ({bonus})',
            'Daily random events': (":warning: " if random_events < 10 else "") + f'{random_events}/10',
            'Daily elites': f'{elites}/400',
            'Weekly bosses': (":warning: " if weekly_bosses < 3 else "") + f'{weekly_bosses}/3',
            'Weekly bounties': (":warning: " if weekly_bounties < 3 else "") + f'{weekly_bounties}/3',
        }

        pt = session.get(ScheduledItem, (uid, ItemType.PARAMETRIC_TRANSFORMER))
        if pt and not pt.done:
            data['Parametric transformer'] = f"<t:{int(pt.scheduled_at.replace(tzinfo=pytz.UTC).timestamp())}>"
        else:
            data['Parametric transformer'] = ":warning: not scheduled"

        return data
