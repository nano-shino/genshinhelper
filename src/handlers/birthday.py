import asyncio
import datetime
import random
from io import BytesIO

import aiohttp
import discord
import pytz
from dateutil.relativedelta import relativedelta
from discord import Option, SlashCommandGroup
from discord.ext import commands, tasks, pages
from sqlalchemy import select

from common import guild_level, autocomplete
from common.db import session
from common.logging import logger
from datamodels.birthday import Birthday
from datamodels.guild_settings import GuildSettingKey
from handlers import guild_manager


class BirthdayHandler(commands.Cog):
    birthday = SlashCommandGroup(
        "birthday", "Birthday reminders", guild_ids=guild_level.get_guild_ids(level=1)
    )

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.guild_manager = guild_manager.GuildSettingManager()
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            await self.birthday_reminder()
            now = datetime.datetime.now()
            wait_in_seconds = (
                (now + relativedelta(hours=1, minute=0, second=0)) - now
            ).total_seconds()
            logger.info(
                f"Birthday reminder task loop is scheduled to start in {wait_in_seconds} seconds"
            )
            await asyncio.sleep(wait_in_seconds)
            self.birthday_reminder_loop.start()
            self.start_up = True

    @tasks.loop(hours=1, reconnect=False)
    async def birthday_reminder_loop(self):
        await self.birthday_reminder()

    async def birthday_reminder(self):
        for bday in session.execute(select(Birthday)).scalars():
            now = datetime.datetime.now(pytz.timezone(bday.timezone))

            if (
                bday.reminded_at
                and (datetime.datetime.utcnow() - bday.reminded_at).days < 180
            ):
                continue

            if now.month != bday.month or now.day != bday.day:
                continue

            logger.info(f"Today is {bday.discord_id}'s birthday!")

            guild = self.bot.get_guild(bday.guild_id)
            channel_id = self.guild_manager.get_entry(
                bday.guild_id, GuildSettingKey.BOT_CHANNEL
            )

            if not channel_id:
                logger.warning(f"Channel ID not set for guild {guild.name}:{guild.id}")
                continue

            channel = await guild.fetch_channel(channel_id)
            member = await guild.fetch_member(bday.discord_id)

            await channel.send(f":birthday: Today is {member.mention}'s birthday!")

            bday.reminded_at = datetime.datetime.utcnow()
            session.commit()

    @birthday.command(
        description="Adds your birthday",
    )
    async def set(
        self,
        ctx: discord.ApplicationContext,
        month: Option(int, "A number 1-12", min_value=1, max_value=12),
        day: Option(
            int,
            "A number 1-31 (unless the month is shorter)",
            min_value=1,
            max_value=31,
        ),
        timezone: Option(
            str,
            "Use the most popular city in your timezone",
            autocomplete=autocomplete.fuzzy_autocomplete(pytz.common_timezones),
        ),
        member: Option(discord.Member, "Discord ID", required=False),
    ):
        if member and (
            not ctx.author.guild_permissions.administrator or member.id == ctx.author.id
        ):
            await ctx.respond(f"You can only set your own birthday", ephemeral=True)
            return

        member = member or ctx.author

        now = datetime.datetime.now()

        try:
            datetime.date(month=month, day=day, year=now.year)
        except ValueError:
            await ctx.respond(f":warning: Invalid month/day", ephemeral=True)
            return

        try:
            pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            await ctx.respond(
                f":warning: Invalid timezone. Use https://kevinnovak.github.io/Time-Zone-Picker/ for help",
                ephemeral=True,
            )
            return

        session.merge(
            Birthday(
                discord_id=member.id,
                guild_id=ctx.guild_id,
                month=month,
                day=day,
                timezone=timezone,
            )
        )
        session.commit()

        days_util = (now + relativedelta(month=month, day=day) - now).days

        if days_util < 0:
            days_util = (now + relativedelta(years=1, month=month, day=day) - now).days

        await ctx.respond(
            f":white_check_mark: {days_util} days until {member.name}'s birthday"
        )

    @birthday.command(
        description="Removes your birthday",
    )
    async def remove(
        self,
        ctx: discord.ApplicationContext,
        member: Option(
            discord.Member,
            "Discord ID (only guild admins can use this)",
            required=False,
        ),
    ):
        if member and (
            not ctx.author.guild_permissions.administrator or member.id == ctx.author.id
        ):
            await ctx.respond(f"You can only remove your own birthday", ephemeral=True)
            return

        member = member or ctx.author

        record = session.get(Birthday, (member.id, ctx.guild_id))

        if record:
            session.delete(record)
            session.commit()
            message = f"Birthday for member {member.mention} has been removed"
        else:
            message = f"Birthday for member {member.mention} was not found"

        await ctx.respond(embed=discord.Embed(description=message))

    @birthday.command(description="Lists all birthdays")
    async def list(
        self,
        ctx: discord.ApplicationContext,
    ):
        await ctx.defer()

        bdays = []

        for bday in session.execute(
            select(Birthday).where(Birthday.guild_id == ctx.guild_id)
        ).scalars():
            now = datetime.datetime.now(pytz.timezone(bday.timezone))
            date = relativedelta(
                month=bday.month,
                day=bday.day,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            if now + date < now:
                date.years = 1
            delta = now + date - now
            offset = (now + date).strftime("%z")
            bdays.append((delta, bday.discord_id, date, offset))

        if not bdays:
            await ctx.send_followup("No birthday found")
            return

        bdays.sort()

        lines = []
        for delta, discord_id, date, offset in bdays:
            lines.append(
                f"{date.month}/{date.day} <@{discord_id}> `{offset[:3]}:{offset[3:]}`"
            )

        embeds = []
        while lines:
            embed = discord.Embed(description="\n".join(lines[:10]))
            lines = lines[10:]
            embeds.append(embed)

        paginator = pages.Paginator(
            pages=embeds, show_disabled=True, show_indicator=True, author_check=False
        )

        await paginator.respond(ctx.interaction)

    _BIRTHDAY_VOICELINES = {
        "Arataki_Itto": "https://static.wikia.nocookie.net/gensin-impact/images/7/72/VO_Arataki_Itto_Birthday.ogg",
        "Gorou": "https://static.wikia.nocookie.net/gensin-impact/images/3/3c/VO_Gorou_Birthday.ogg",
    }

    async def get_random_voiceline(self):
        async with aiohttp.ClientSession() as session:
            name, url = random.choice(list(self._BIRTHDAY_VOICELINES.items()))
            async with session.get(url) as response:
                ogg_file = await response.read()
                return name, BytesIO(ogg_file)
