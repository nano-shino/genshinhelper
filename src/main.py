from collections import defaultdict

import discord
from discord.ext import commands
from discord.ext.commands import Command
from sqlalchemy import select

from common import conf, db
from common.db import session
from datamodels import Base
from datamodels.guild_settings import GuildSettings, GuildSettingKey
from handlers import all_handlers, prefix_commands
from scheduling import dispatcher
from utils.unified_context import UnifiedContext


DEFAULT_PREFIX = "!"
guild_prefix_lookup = defaultdict(lambda: DEFAULT_PREFIX)


# Custom command prefix for each guild
def get_prefix(bot: discord.Bot, message: discord.Message):
    if message.guild:
        return guild_prefix_lookup[message.guild.id]
    return DEFAULT_PREFIX


bot = commands.Bot(command_prefix=get_prefix)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="Jenshin Impact"))

    for setting in session.execute(
        select(GuildSettings).where(GuildSettings.key == GuildSettingKey.COMMAND_PREFIX)
    ).scalars():
        guild_prefix_lookup[setting.guild_id] = setting.value


@bot.event
async def on_application_command_error(ctx, error):
    embed = discord.Embed(
        title=":x: Command error",
        description=error.original
    )
    await ctx.send_followup(embed=embed, delete_after=60)


@bot.event
async def on_command_error(ctx, error):
    embed = discord.Embed(
        title=":x: Command error",
        description=error.original
    )
    await ctx.send(embed=embed, delete_after=60)


if __name__ == "__main__":
    # Creates database
    Base.metadata.create_all(bind=db.engine)

    # Initializes all handlers
    for handler in all_handlers:
        bot.add_cog(handler(bot=bot))
    bot.add_cog(dispatcher.Dispatcher(bot=bot))

    # Supports prefix commands via a hacky way
    # This should be removed once slash commands work better on mobile.
    for cog_class, commands in prefix_commands:
        cog = bot.get_cog(cog_class.__cog_name__)
        for command in commands:

            async def _handler(ctx, *args, **kwargs):
                await getattr(cog, command).callback(
                    cog, UnifiedContext(ctx), *args, **kwargs
                )

            bot.add_command(Command(_handler, name=command))

    # Starts the bot
    bot.run(conf.DISCORD_BOT_TOKEN)
