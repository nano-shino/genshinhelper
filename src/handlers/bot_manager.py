import discord
from discord import SlashCommandGroup
from discord.ext import commands

from common import guild_level
from interfaces.route_loader import load_images


class BotCommandHandler(commands.Cog):
    bot = SlashCommandGroup(
        "bot",
        "Bot-related commands",
        guild_ids=guild_level.get_guild_ids(level=5))

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            await load_images(self.bot)
            self.start_up = True

    @bot.command(
        description="Reloads route images",
        guild_ids=guild_level.get_guild_ids(level=5),
    )
    async def reload_routes(self, ctx):
        count = await load_images(self.bot)
        await ctx.respond(f"Reloaded {count} images")

    @bot.command(
        description="Shows heartbeat latency",
        guild_ids=guild_level.get_guild_ids(level=5),
    )
    async def latency(self, ctx):
        await ctx.respond(f"Latency: {self.bot.latency*1000:.0f}ms")
