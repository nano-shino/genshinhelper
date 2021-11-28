from discord.ext import commands

from common import conf

bot = commands.Bot(command_prefix="!")


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


if __name__ == '__main__':
    bot.run(conf.DISCORD_BOT_TOKEN)
