import asyncio
import os
import pathlib
import sys

import discord
from discord import SlashCommandGroup
from discord.ext import commands

from common import guild_level
from common.logging import logger
from interfaces.route_loader import load_images


class BotCommandHandler(commands.Cog):
    bot = SlashCommandGroup(
        "bot", "Bot-related commands", guild_ids=guild_level.get_guild_ids(level=5)
    )

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            await load_images(self.bot)
            self.start_up = True

    @bot.command(
        description="Restarts the bot",
        guild_ids=guild_level.get_guild_ids(level=5),
    )
    async def restart(self, ctx):
        await ctx.respond("Restarting...")
        args = [sys.executable] + sys.argv
        logger.info(f"Restarting the bot: {args}")
        os.execv(sys.executable, args)

    @bot.command(
        description="Updates the bot",
        guild_ids=guild_level.get_guild_ids(level=5),
    )
    async def update(self, ctx):
        await ctx.defer()
        logger.info("Updating the bot")

        async def _run_command(*args):
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(__file__),
            )

            stdout, stderr = await proc.communicate()

            logger.info(f"Command git pull exited with {proc.returncode}")

            if stdout:
                logger.info(f"[stdout]\n{stdout.decode()}")
            if stderr:
                logger.critical(f"[stderr]\n{stderr.decode()}")

        await _run_command("git", "pull")
        await _run_command(sys.executable, "-m", "pip", "install", "-r", pathlib.Path("requirements.txt").resolve())
        await ctx.edit(content="Bot updated")
        os.execv(sys.executable, [sys.executable] + sys.argv)

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
