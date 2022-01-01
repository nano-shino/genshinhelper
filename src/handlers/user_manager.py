import dataclasses

import discord
import genshin.errors
from discord import Option, ApplicationContext, SlashCommandGroup, SelectOption
from discord.ext import commands
from sqlalchemy import select
from tenacity import wait_fixed, stop_after_attempt, retry, retry_if_exception_type

from common import conf
from common.db import session
from common.logging import logger
from datamodels.account_settings import AccountInfo, Preferences, DEFAULT_SETTINGS
from datamodels.genshin_user import GenshinUser, TokenExpiredError
from datamodels.uid_mapping import UidMapping
from handlers.parametric_transformer import scan_account


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
        account = session.get(GenshinUser, (ltuid,))

        if account:
            if account.discord_id != ctx.author.id:
                await ctx.edit(content="Account already registered to another Discord user. They must unbind first.")
                return
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
                session.add(UidMapping(uid=main_account.uid, mihoyo_id=account.mihoyo_id, main=True))
                messages += [f"Account {main_account.nickname} will be set as your main"]
                session.commit()
                session.flush(account)

            await self.enable_real_time_notes(gs, account.genshin_uids[0])
            await gs.session.close()

        messages += [f"Registration complete!"]
        await ctx.edit(content="\n".join(messages))

        # Scan parametric transformer usage last 7 days (roughly) because the user just registered and missed the
        # daily scan.
        await scan_account(self.bot, account, 24 * 6 + 10)

    @user.command(
        description="Enable or disable certain features."
    )
    async def settings(self, ctx: ApplicationContext):
        await ctx.defer(ephemeral=True)
        for account in session.execute(select(GenshinUser).where(GenshinUser.discord_id == ctx.author.id)).scalars():
            gs = genshin.GenshinClient(account.cookies)
            user_info = await gs.request_hoyolab(f"community/user/wapi/getUserFullInfo?uid={account.mihoyo_id}")
            await gs.session.close()
            await ctx.send_followup(f"Account **{user_info['user_info']['nickname']}** ({account.mihoyo_id}) settings:",
                                    view=PreferencesView(account.mihoyo_id), ephemeral=True)

    @retry(retry=retry_if_exception_type(genshin.errors.DataNotPublic), stop=stop_after_attempt(5), wait=wait_fixed(5))
    async def enable_real_time_notes(self, client: genshin.GenshinClient, uid: int):
        result = await client.request_game_record(
            "card/wapi/changeDataSwitch",
            method="POST",
            json=dict(is_public=True, game_id=2, switch_id=3),
        )
        logger.info(f"Enabling resin data for uid={uid}. Response: {result}")
        await client.get_notes(uid)


@dataclasses.dataclass
class PreferenceOption:
    label: str
    description: str
    value: str


ALL_PREFERENCES = [
    PreferenceOption(
        label='Daily checkin',
        description='Auto check-in and notify you',
        value=Preferences.DAILY_CHECKIN),
    PreferenceOption(
        label='Resin cap',
        description='Send you a message when your resin is capped',
        value=Preferences.RESIN_REMINDER),
    PreferenceOption(
        label='Parametric Transformer',
        description='Send you a message when your parametric transformer is ready',
        value=Preferences.PARAMETRIC_TRANSFORMER),
]


class PreferencesDropdown(discord.ui.Select['Preferences']):
    def __init__(self, mihoyo_id):
        super().__init__()
        self.mihoyo_id = mihoyo_id
        self.placeholder = 'No features enabled'
        self.record = session.get(AccountInfo, (mihoyo_id,))
        if not self.record:
            self.record = AccountInfo(id=mihoyo_id, settings=DEFAULT_SETTINGS)

        self.options = [
            SelectOption(
                label=pref.label, description=pref.description,
                value=pref.value, default=self.record.settings[pref.value])
            for pref in ALL_PREFERENCES
        ]

        self.min_values = 0
        self.max_values = len(self.options)

    async def callback(self, interaction: discord.Interaction):
        settings = self.record.settings
        for name in settings:
            settings[name] = name in self.values
        self.record.settings = settings
        session.merge(self.record)
        session.commit()


class PreferencesView(discord.ui.View):
    def __init__(self, mihoyo_id: int):
        super().__init__()
        self.add_item(PreferencesDropdown(mihoyo_id))
