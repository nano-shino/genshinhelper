import discord
from discord.ext import commands

from common import conf
from handlers import all_handlers

bot = commands.Bot(command_prefix="!")


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="Jenshin Impact"))


if __name__ == '__main__':
    # Init all handlers
    for handler in all_handlers:
        bot.add_cog(handler(bot=bot))

    # Start the bot
    bot.run(conf.DISCORD_BOT_TOKEN)
