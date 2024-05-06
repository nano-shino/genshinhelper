from typing import List

import discord
from discord.ext import commands
from sqlalchemy import select

from common.db import session
from datamodels.genshin_user import GenshinUser


class BaseHandler(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    async def get_default_uid(self, ctx: discord.ApplicationContext):
        accounts: List[GenshinUser] = (
            session.execute(
                select(GenshinUser).where(GenshinUser.discord_id == ctx.author.id)
            )
                .scalars()
                .all()
        )

        if not accounts:
            await ctx.respond("You don't have any registered accounts with this bot.")
            return

        for account in accounts:
            if account.main_genshin_uid:
                return account.main_genshin_uid
            elif account.genshin_uids:
                return account.genshin_uids[0]

        return None
