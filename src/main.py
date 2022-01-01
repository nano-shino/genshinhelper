import discord
from discord.ext import commands

from common import conf, db
from datamodels import Base
from handlers import all_handlers
from scheduling import dispatcher

bot = commands.Bot(command_prefix="!")


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="Jenshin Impact"))


if __name__ == '__main__':
    # Create database
    Base.metadata.create_all(bind=db.engine)

    # Init all handlers
    for handler in all_handlers:
        bot.add_cog(handler(bot=bot))
    bot.add_cog(dispatcher.Dispatcher(bot=bot))

    # Start the bot
    bot.run(conf.DISCORD_BOT_TOKEN)
