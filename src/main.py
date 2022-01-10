import discord
from discord.ext import commands
from discord.ext.commands import Command

from common import conf, db
from datamodels import Base
from handlers import all_handlers, prefix_commands
from scheduling import dispatcher
from utils.unified_context import UnifiedContext

bot = commands.Bot(command_prefix="!")


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="Jenshin Impact"))


if __name__ == '__main__':
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
                await getattr(cog, command).callback(cog, UnifiedContext(ctx), *args, **kwargs)

            bot.add_command(Command(_handler, name=command))

    # Starts the bot
    bot.run(conf.DISCORD_BOT_TOKEN)
