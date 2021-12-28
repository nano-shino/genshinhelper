import datetime

import discord
import pytz
from dateutil.relativedelta import relativedelta
from discord import Option, SlashCommandGroup
from discord.ext import commands, tasks, pages

from common import conf
from common.db import conn
from common.logging import logger
from handlers import guild_manager


class BirthdayHandler(commands.Cog):

    birthday = SlashCommandGroup(
        "birthday",
        "Birthday reminders",
        guild_ids=conf.DISCORD_GUILD_IDS)

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.guild_manager = guild_manager.GuildSettingManager()
        with conn:
            conn.execute("create table if not exists bday ("
                         "  discord_id integer not null,"
                         "  guild_id integer not null,"
                         "  month integer,"
                         "  day integer,"
                         "  timezone text,"
                         "  reminded_at text,"
                         "  primary key (discord_id, guild_id)"
                         ")")

    @commands.Cog.listener()
    async def on_ready(self):
        self.birthday_reminder.start()

    @tasks.loop(hours=1)
    async def birthday_reminder(self):
        with conn:
            results = conn.execute("select * from bday").fetchall()

        for discord_id, guild_id, month, day, timezone, reminded_at in results:
            if reminded_at and (datetime.datetime.fromisoformat(reminded_at) - datetime.datetime.now()).days < 180:
                continue

            today = datetime.datetime.now(pytz.timezone(timezone))

            if today.month != month or today.day != day:
                continue

            guild = self.bot.get_guild(guild_id)
            channel_id = self.guild_manager.get_entry(guild_id, guild_manager.GuildSettings.BOT_CHANNEL.value)

            if not channel_id:
                logger.warning(f"Channel ID not set for guild {guild.name}:{guild.id}")
                continue

            channel = await guild.fetch_channel(channel_id)

            member = await guild.fetch_member(discord_id)

            with conn:
                conn.execute("update bday set reminded_at=? where discord_id=? and guild_id=?",
                             (datetime.datetime.now().isoformat(), discord_id, guild_id))

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

        with conn:
            conn.execute("insert or replace into bday values (?, ?, ?, ?, ?, ?)",
                         (member.id, ctx.guild_id, month, day, timezone, None))

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

        with conn:
            for discord_id, guild_id, month, day, timezone, reminded_at in conn.execute("select * from bday"):
                now = datetime.datetime.now(pytz.timezone(timezone))
                date = relativedelta(month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
                if now + date < now:
                    date.years = 1
                delta = now + date - now
                offset = (now + date).strftime('%z')
                bdays.append((delta, discord_id, date, offset))

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
