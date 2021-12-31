import discord
from discord import Option, ApplicationContext, SlashCommandGroup
from discord.ext import commands

from common import conf
from common.db import session
from datamodels.genshin_user import GenshinUser, TokenExpiredError


class UserManager(commands.Cog):
    user = SlashCommandGroup(
        "user",
        "User-related commands",
        guild_ids=conf.DISCORD_GUILD_IDS)

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @user.command(
        description="Register a Genshin account"
    )
    async def register(
            self,
            ctx: ApplicationContext,
            ltuid: Option(int, "Mihoyo account ID"),
            ltoken: Option(str, "Hoyolab login token", required=False),
            authkey: Option(str, "Wish history auth key", required=False),
            cookie_token: Option(str, "genshin.mihoyo.com cookie_token", required=False)
    ):
        await ctx.respond(f"Looking up your account...", ephemeral=True)

        discord_id = ctx.author.id
        account = session.get(GenshinUser, (discord_id, ltuid))

        if account:
            await ctx.edit(content="Found existing account in database")
        else:
            account = GenshinUser(discord_id=discord_id, mihoyo_id=ltuid)

        if ltoken:
            account.hoyolab_token = ltoken
        if cookie_token:
            account.mihoyo_token = cookie_token
        if authkey:
            account.mihoyo_authkey = authkey

        session.merge(account)
        session.commit()

        messages = []

        try:
            async for item in account.validate():
                messages += [f":white_check_mark: {item} is valid"]
                await ctx.edit(content="\n".join(messages))
        except TokenExpiredError as e:
            messages += [f":x: {e}"]
            await ctx.edit(content="\n".join(messages))
            session.commit()

        if account.hoyolab_token:
            gs = account.client
            accounts = await gs.genshin_accounts()
            if not account.genshin_uids and accounts:
                main_account = max(accounts, key=lambda acc: acc.level)
                account.genshin_uids = [main_account.uid]
                messages += [f"Account {main_account.nickname} will be set as your main"]
                session.merge(account)
                session.commit()

        messages += [f"Registration complete"]
        await ctx.edit(content="\n".join(messages))
