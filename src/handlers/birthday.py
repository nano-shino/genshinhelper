import datetime

import discord
import pytz
from dateutil.relativedelta import relativedelta
from discord import Option, SlashCommandGroup
from discord.ext import commands, tasks, pages
from sqlalchemy import select

from common import conf
from common.db import session
from common.logging import logger
from datamodels.birthday import Birthday
from handlers import guild_manager


class BirthdayHandler(commands.Cog):
    birthday = SlashCommandGroup(
        "birthday",
        "Birthday reminders",
        guild_ids=conf.DISCORD_GUILD_IDS)

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.guild_manager = guild_manager.GuildSettingManager()
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            self.birthday_reminder.start()
            self.start_up = True

    @tasks.loop(hours=1)
    async def birthday_reminder(self):
        for bday in session.execute(select(Birthday)).scalars():
            now = datetime.datetime.now(pytz.timezone(bday.timezone))

            if bday.reminded_at and (datetime.datetime.utcnow() - bday.reminded_at).days < 180:
                continue

            if now.month != bday.month or now.day != bday.day:
                continue

            guild = self.bot.get_guild(bday.guild_id)
            channel_id = self.guild_manager.get_entry(bday.guild_id, guild_manager.GuildSettingKey.BOT_CHANNEL.value)

            if not channel_id:
                logger.warning(f"Channel ID not set for guild {guild.name}:{guild.id}")
                continue

            channel = await guild.fetch_channel(channel_id)
            member = await guild.fetch_member(bday.discord_id)

            bday.reminded_at = datetime.datetime.utcnow()
            session.commit()

            await channel.send(f":birthday: Today is {member.mention}'s birthday!")

    @birthday.command(
        description="Add your birthday",
    )
    async def set(
            self,
            ctx,
            month: Option(int, "Month", min_value=1, max_value=12),
            day: Option(int, "Day", min_value=1, max_value=31),
            timezone: Option(str, "Timezone https://kevinnovak.github.io/Time-Zone-Picker/",
                             autocomplete=discord.utils.basic_autocomplete(pytz.common_timezones)),
            member: Option(discord.Member, "Discord ID", required=False),
    ):
        if member and (not ctx.author.guild_permissions.administrator or member.id == ctx.author.id):
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
                ephemeral=True)
            return

        session.merge(Birthday(discord_id=member.id, guild_id=ctx.guild_id, month=month, day=day, timezone=timezone))
        session.commit()

        days_util = (now + relativedelta(month=month, day=day) - now).days

        if days_util < 0:
            days_util = (now + relativedelta(years=1, month=month, day=day) - now).days

        await ctx.respond(f":white_check_mark: {days_util} days until {member.name}'s birthday")

    @birthday.command(
        description="List all birthdays"
    )
    async def list(
            self,
            ctx
    ):
        await ctx.defer()

        bdays = []

        for bday in session.execute(select(Birthday)).scalars():
            now = datetime.datetime.now(pytz.timezone(bday.timezone))
            date = relativedelta(month=bday.month, day=bday.day, hour=0, minute=0, second=0, microsecond=0)
            if now + date < now:
                date.years = 1
            delta = now + date - now
            offset = (now + date).strftime('%z')
            bdays.append((delta, bday.discord_id, date, offset))

        bdays.sort()

        lines = []
        for delta, discord_id, date, offset in bdays:
            lines.append(f"{date.month}/{date.day} <@{discord_id}> `{offset[:3]}:{offset[3:]}`")

        embeds = []
        while lines:
            embed = discord.Embed(description="\n".join(lines[:10]))
            lines = lines[10:]
            embeds.append(embed)

        paginator = pages.Paginator(pages=embeds, show_disabled=True, show_indicator=True, author_check=False)
        paginator.customize_button("next", button_label=">", button_style=discord.ButtonStyle.blurple)
        paginator.customize_button("prev", button_label="<", button_style=discord.ButtonStyle.blurple)
        paginator.customize_button("first", button_label="<<", button_style=discord.ButtonStyle.gray)
        paginator.customize_button("last", button_label=">>", button_style=discord.ButtonStyle.gray)

        await paginator.respond(ctx)
