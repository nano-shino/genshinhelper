import asyncio
import logging
from datetime import datetime
from typing import List, Optional

import discord
import genshin
from dateutil.relativedelta import relativedelta
from discord.ext import tasks, commands
from genshin import Game
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential

from common.conf import DAILY_CHECKIN_GAMES
from common.constants import Preferences
from common.db import session
from common.genshin_server import ServerEnum
from common.logging import logger
from datamodels.genshin_user import GenshinUser
from datamodels.scheduling import ScheduledItem, ItemType


class HoyolabDailyCheckin(commands.Cog):
    DATABASE_KEY = ItemType.DAILY_CHECKIN
    CHECKIN_TIMEZONE = ServerEnum.ASIA
    TASK_INTERVAL_HOURS = 4

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            self.start_up = True

            # To better align with check in time, we schedule the task such that it runs every
            # {TASK_INTERVAL_HOURS} hours and one run will coincide with the checkin reset time.
            next_checkin_time = self.CHECKIN_TIMEZONE.day_beginning + relativedelta(
                day=1
            )
            time_until = (
                next_checkin_time - self.CHECKIN_TIMEZONE.current_time
            ).total_seconds()
            await_seconds = time_until % (self.TASK_INTERVAL_HOURS * 3600)
            logger.info(f"Next daily checkin scan is in {await_seconds} seconds")
            await asyncio.sleep(await_seconds)

            self.job.start()

    @tasks.loop(hours=4, reconnect=False)
    async def job(self):
        logger.info(f"Daily checkin scan begins")
        for discord_id in session.execute(
            select(GenshinUser.discord_id.distinct())
        ).scalars():
            try:
                discord_user = await self.bot.fetch_user(discord_id)
                channel = await discord_user.create_dm()
                await self.checkin(discord_id, channel)
            except Exception:
                logging.exception(f"Cannot check in for {discord_id}")

    async def checkin(self, discord_id: int, channel: discord.DMChannel):
        embeds = []
        failure_embeds = []

        for account in session.execute(
            select(GenshinUser).where(GenshinUser.discord_id == discord_id)
        ).scalars():
            account: GenshinUser

            if not account.hoyolab_token:
                continue

            gs = account.client

            if not account.settings[Preferences.DAILY_CHECKIN]:
                continue

            # Validate cookies
            try:
                await gs.get_reward_info()
            except genshin.errors.InvalidCookies:
                account.hoyolab_token = None
                session.merge(account)
                session.commit()
                failure_embeds.append(discord.Embed(
                    title=":warning: Account Access Failure",
                    description=f"Your ltoken has expired for Hoyolab ID {account.mihoyo_id}.\n"
                                f"This may be because you have changed your password recently.\n"
                                f"Please register again if you want to continue using the bot."
                ))
                continue

            task: Optional[ScheduledItem] = session.get(
                ScheduledItem, (account.mihoyo_id, self.DATABASE_KEY)
            )

            if (
                not task
                or task.scheduled_at
                < self.CHECKIN_TIMEZONE.day_beginning.replace(tzinfo=None)
            ):
                try:
                    claimed_games = await self.claim_reward(gs)
                except Exception:
                    logger.exception("Cannot claim daily rewards")
                    continue
                if claimed_games:
                    embed = discord.Embed()
                    embeds.append(embed)
                    embed.description = (
                        f"Claimed daily rewards for {len(claimed_games)} game{'s' if len(claimed_games) > 1 else ''} "
                        f"({', '.join(game.name.lower() for game in claimed_games)}) | Hoyolab ID {account.mihoyo_id}"
                    )

                    try:
                        for uid in account.genshin_uids:
                            notes = await gs.get_notes(uid)
                            resin_capped = notes.current_resin == notes.max_resin

                            embed.add_field(
                                name=f"{notes.current_resin}/{notes.max_resin} resin",
                                value=":warning: capped OMG"
                                if resin_capped
                                else f"capped <t:{int(notes.resin_recovery_time.timestamp())}:R>",
                            )

                            if notes.expeditions:
                                exp_completed_at = max(exp.completion_time for exp in notes.expeditions)
                                exp_text = (
                                    ":warning: all done"
                                    if exp_completed_at <= datetime.now().astimezone()
                                    else f"done <t:{int(exp_completed_at.timestamp())}:R>"
                                )
                            else:
                                exp_text = ":warning: No ongoing expeditions"

                            embed.add_field(
                                name=f"**{len(notes.expeditions)}/{notes.max_expeditions} expeditions dispatched**",
                                value=exp_text,
                            )
                            
                            embed.description += f"\nUID-`{uid}`"
                    except Exception:
                        logger.exception("Cannot get resin data")

                session.merge(
                    ScheduledItem(
                        id=account.mihoyo_id,
                        type=self.DATABASE_KEY,
                        scheduled_at=self.CHECKIN_TIMEZONE.day_beginning,
                        done=True,
                    )
                )
                session.commit()

        if embeds:
            await channel.send(
                "I've gone ahead and checked in for you. Have a nice day!",
                embeds=embeds,
            )

        if failure_embeds:
            await channel.send(
                embeds=failure_embeds,
            )

    @retry(
        stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=600)
    )
    async def claim_reward(
        self, client: genshin.Client
    ) -> List[Game]:
        checked_in_games = []

        for game_string in DAILY_CHECKIN_GAMES:
            game = Game[game_string]
            try:
                await client.claim_daily_reward(reward=True, game=game)
                checked_in_games.append(game)
            except genshin.errors.DailyGeetestTriggered:
                logger.info("Skipping geetest")
                continue
            except genshin.errors.AlreadyClaimed:
                logger.info(
                    f"Daily reward for {game} is already claimed for {client.hoyolab_id}"
                )
                continue
            except genshin.errors.GenshinException as ex:
                if ex.retcode == -10002:
                    # No account found
                    continue

                logger.exception(
                    f"Cannot claim daily rewards for {game} for {client.hoyolab_id}"
                )
                raise

        return checked_in_games
