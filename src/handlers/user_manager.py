import dataclasses
from typing import List

import discord
import genshin.errors
from discord import Option, ApplicationContext, SlashCommandGroup, SelectOption
from discord.ext import commands
from genshin.models import GenshinAccount
from sqlalchemy import select, delete
from tenacity import wait_fixed, stop_after_attempt, retry, retry_if_exception_type

from common import guild_level
from common.constants import Emoji, Time
from common.db import session
from common.logging import logger
from datamodels.account_settings import Preferences, AccountInfo
from datamodels.genshin_user import GenshinUser, TokenExpiredError
from datamodels.uid_mapping import UidMapping
from handlers.parametric_transformer import scan_account


class UserManager(commands.Cog):
    user = SlashCommandGroup(
        "user",
        "User-related commands",
        guild_ids=guild_level.get_guild_ids(level=2),
    )

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @user.command(
        description="To register a Genshin account with this bot"
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

        messages = []

        try:
            async for item in account.validate():
                messages += [f":white_check_mark: {item} is valid"]
                await ctx.edit(embed=discord.Embed(description="\n".join(messages + [Emoji.LOADING + " verifying..."])))
        except TokenExpiredError as e:
            messages += [f":x: {e}"]
            await ctx.edit(embed=discord.Embed(description="\n".join(messages)))

        if account.hoyolab_token:
            gs = account.client
            accounts = await gs.genshin_accounts()
            if not account.genshin_uids and accounts:
                main_account = max(accounts, key=lambda acc: acc.level)
                session.merge(UidMapping(uid=main_account.uid, mihoyo_id=account.mihoyo_id, main=True))
                messages += [f"Account {main_account.nickname} will be set as your main"]

            try:
                await self.enable_real_time_notes(gs)
            except genshin.errors.InvalidCookies as e:
                messages += [":x: " + e.msg]
                if e.retcode == 10103:
                    messages += ["You can go to this link to create a Hoyolab account. "
                                 "[Hoyolab game record](https://webstatic-sea.mihoyo.com/app/community-game-records-sea"
                                 "/index.html?bbs_presentation_style=fullscreen&bbs_auth_required=true&v=101"
                                 f"&gid=2&user_id={ltuid}&bbs_theme=dark&bbs_theme_device=1#/ys)"]
                await ctx.edit(embed=discord.Embed(description="\n".join(messages)))
                raise e
            finally:
                await gs.session.close()

        session.commit()
        messages += ["", "Registration complete!"]
        embed = discord.Embed(description="\n".join(messages))
        embed.set_footer(text="Note that if you change your password, the token will no longer be valid "
                              "and the bot will lose access to your account.")
        await ctx.edit(embed=embed)

        # Scan parametric transformer usage last 7 days (roughly) because the user just registered and missed the
        # daily scan.
        await scan_account(self.bot, account, Time.PARAMETRIC_TRANSFORMER_COOLDOWN.total_seconds() // 3600)

    @user.command(
        description="To enable or disable certain features"
    )
    async def settings(self, ctx: ApplicationContext):
        await ctx.defer(ephemeral=True)

        accounts = session.execute(select(GenshinUser).where(GenshinUser.discord_id == ctx.author.id)).scalars().all()

        if not accounts:
            await ctx.send_followup("You don't have any registered accounts with this bot.")
            return

        for account in accounts:
            gs = account.client
            accounts = await gs.genshin_accounts()
            user_info = await gs.request_hoyolab(f"community/user/wapi/getUserFullInfo?uid={account.mihoyo_id}")
            await gs.session.close()
            embed = discord.Embed(
                title=f"Account {user_info['user_info']['nickname']} ({account.mihoyo_id})",
                description=f"The first box is the features you can enable, while the second box will restrict "
                            f"what UIDs the bot can see in your account.\n"
                            f"Hiding a UID may be handy if you don't want it to show up in commands like resin "
                            f"check or resin cap notification."
            )
            await ctx.send_followup(
                embed=embed,
                view=PreferencesView(account.mihoyo_id, ctx.guild.id, accounts),
                ephemeral=True)

    @retry(retry=retry_if_exception_type(genshin.errors.DataNotPublic), stop=stop_after_attempt(5), wait=wait_fixed(5))
    async def enable_real_time_notes(self, client: genshin.GenshinClient):
        result = await client.request_game_record(
            "card/wapi/changeDataSwitch",
            method="POST",
            json=dict(is_public=True, game_id=2, switch_id=3),
        )
        logger.info(f"Enabling resin data. Response: {result}")
        accounts = await client.genshin_accounts()
        await client.get_notes(accounts[0].uid)


@dataclasses.dataclass
class PreferenceOption:
    label: str
    description: str
    value: str
    guild_level: int


ALL_PREFERENCES = [
    PreferenceOption(
        label='Daily checkin',
        description='Auto check-in and notify you',
        value=Preferences.DAILY_CHECKIN,
        guild_level=3),
    PreferenceOption(
        label='Resin cap',
        description='Send you a message when your resin is capped',
        value=Preferences.RESIN_REMINDER,
        guild_level=2),
    PreferenceOption(
        label='Parametric Transformer',
        description='Send you a message when your parametric transformer is ready',
        value=Preferences.PARAMETRIC_TRANSFORMER,
        guild_level=2),
]


class PreferencesDropdown(discord.ui.Select['Preferences']):
    def __init__(self, mihoyo_id: int, guild_id: int):
        super().__init__()
        self.mihoyo_id = mihoyo_id
        self.placeholder = 'No features enabled'
        self.account = session.get(GenshinUser, (mihoyo_id,))

        glevel = guild_level.get_guild_level(guild_id)

        if not self.account:
            logger.critical("Account might have been deleted")
            return

        self.options = [
            SelectOption(
                label=pref.label, description=pref.description,
                value=pref.value, default=self.account.settings[pref.value])
            for pref in ALL_PREFERENCES if glevel >= pref.guild_level
        ]

        self.min_values = 0
        self.max_values = len(self.options)

    async def callback(self, interaction: discord.Interaction):
        settings = self.account.settings

        for option in self.options:
            settings[option.value] = False
        for value in self.values:
            settings[value] = True

        account_info = AccountInfo(id=self.account.mihoyo_id, settings=settings)
        session.merge(account_info)
        session.commit()


class UidDropdown(discord.ui.Select['UidSettings']):
    def __init__(self, mihoyo_id: int, accounts: List[GenshinAccount]):
        super().__init__()
        self.mihoyo_id = mihoyo_id
        self.accounts = accounts
        self.placeholder = 'Choose the UIDs you want to use with this bot'
        current_uids = session.execute(select(UidMapping.uid).where(UidMapping.mihoyo_id == mihoyo_id)).scalars().all()

        self.options = [
            SelectOption(
                label=str(account.uid), description=f"{account.server_name} - {account.nickname} AR{account.level}",
                value=str(account.uid), default=account.uid in current_uids)
            for account in self.accounts
        ]

        self.min_values = 0
        self.max_values = len(self.options)

    async def callback(self, interaction: discord.Interaction):
        selected_uids = list(map(int, self.values))
        session.execute(
            delete(UidMapping).where(UidMapping.mihoyo_id == self.mihoyo_id, UidMapping.uid.not_in(selected_uids))
        )
        session.commit()

        accounts = sorted(
            [account for account in self.accounts if account.uid in selected_uids], key=lambda acc: acc.level)
        for uid in selected_uids:
            session.merge(UidMapping(uid=uid, mihoyo_id=self.mihoyo_id, main=uid == accounts[-1].uid))

        session.commit()


class PreferencesView(discord.ui.View):
    def __init__(self, mihoyo_id: int, guild_id: int, accounts: List[GenshinAccount]):
        super().__init__()
        self.add_item(PreferencesDropdown(mihoyo_id, guild_id))
        self.add_item(UidDropdown(mihoyo_id, accounts))
