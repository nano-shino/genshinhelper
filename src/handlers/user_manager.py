import dataclasses
import json
from typing import List

import discord
import genshin.errors
from discord import (
    Option,
    ApplicationContext,
    SlashCommandGroup,
    SelectOption,
)
from discord.ext import commands
from genshin import Game
from genshin.models import GenshinAccount
from sqlalchemy import select, delete, func
from tenacity import wait_fixed, stop_after_attempt, retry, retry_if_exception_type

from common import guild_level
from common.autocomplete import get_account_suggestions
from common.constants import Emoji, Time, Preferences
from common.db import session
from common.logging import logger
from datamodels.account_settings import AccountInfo
from datamodels.genshin_user import GenshinUser, TokenExpiredError
from datamodels.uid_mapping import UidMapping


HELP_EMBED = discord.Embed(
    title="Genshin account linking guide",
    description="""
1. Open https://www.hoyolab.com in an Incognito tab and log in
2. Open Inspect with F12 or right click
3. Go to Application tab. Then click on Cookies and search for "lt"
4. Use the cookies ltmid_v2, ltoken_v2, and ltuid_v2 to create a command like this: /user register ltmid_v2:... ltoken_v2:v2_ABC ltuid_v2:10123456
""".strip()
)


class UserManager(commands.Cog):
    user = SlashCommandGroup(
        "user",
        "User-related commands",
    )

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @user.command(description="Link a Genshin account. For help use the command without arguments.")
    async def register(
            self,
            ctx: ApplicationContext,
            ltmid_v2: Option(str, "Hoyolab login token v2", required=False),
            ltoken_v2: Option(str, "Hoyolab login token v2", required=False),
            ltuid_v2: Option(int, "Mihoyo account ID v2", required=False),
            cookie_token_v2: Option(str, "genshin.hoyoverse.com cookie_token v2", required=False),
    ):
        ltuid = ltuid_v2
        ltoken = json.dumps({"ltoken_v2": ltoken_v2, "ltmid_v2": ltmid_v2}, separators=(',', ':'))
        cookie_token = cookie_token_v2

        if not (ltuid and (ltoken or cookie_token)):
            await ctx.respond(embed=HELP_EMBED)
            return

        await ctx.respond(f"Looking up your account...", ephemeral=True)

        discord_id = ctx.author.id
        try:
            self._validate_discord_user(discord_id, ltuid)
        except ValidationError as e:
            await ctx.edit(content=e.msg)
            return

        account = session.get(GenshinUser, (ltuid,))
        if account:
            if account.discord_id != ctx.author.id:
                await ctx.edit(
                    content="Account already linked to another Discord user. They must unlink it first."
                )
                return
            await ctx.edit(content="Found existing account in database")
        else:
            account = GenshinUser(discord_id=discord_id, mihoyo_id=ltuid)

        if ltoken:
            account.hoyolab_token = ltoken
        if cookie_token:
            account.mihoyo_token = cookie_token

        session.merge(account)

        messages = []

        try:
            async for item in account.validate():
                messages += [f":white_check_mark: {item} is valid"]
                await ctx.edit(
                    embed=discord.Embed(
                        description="\n".join(
                            messages + [Emoji.LOADING + " verifying..."]
                        )
                    )
                )
        except TokenExpiredError as e:
            messages += [f":x: {e}"]
            await ctx.edit(embed=discord.Embed(description="\n".join(messages)))

        if account.hoyolab_token:
            gs = account.client
            accounts = await gs.get_game_accounts()
            accounts = [account for account in accounts if account.game == Game.GENSHIN]
            if not account.genshin_uids and accounts:
                main_account = max(accounts, key=lambda acc: acc.level)
                session.merge(
                    UidMapping(
                        uid=main_account.uid, mihoyo_id=account.mihoyo_id, main=True
                    )
                )
                messages += [
                    f"Account {main_account.nickname} will be set as your main"
                ]

            try:
                await self.enable_real_time_notes(gs, account.main_genshin_uid)
            except genshin.errors.InvalidCookies as e:
                messages += [":x: " + e.msg]
                if e.retcode == 10103:
                    messages += [
                        "You can go to this link to create a Hoyolab account. "
                        "[Hoyolab game record](https://webstatic-sea.hoyoverse.com/app/community-game-records-sea"
                        "/index.html?bbs_presentation_style=fullscreen&bbs_auth_required=true&v=101"
                        f"&gid=2&user_id={ltuid}&bbs_theme=dark&bbs_theme_device=1#/ys)"
                    ]
                await ctx.edit(embed=discord.Embed(description="\n".join(messages)))
                raise e

        session.commit()
        messages += ["", "Registration complete!"]
        embed = discord.Embed(description="\n".join(messages))
        embed.set_footer(
            text="Note that if you change your password, the token will no longer be valid "
                 "and the bot will lose access to your account."
        )
        await ctx.edit(embed=embed)

    @user.command(
        description="To remove a Genshin account registered with this bot",
        guild_ids=guild_level.get_guild_ids(level=3),
    )
    async def delete(
            self,
            ctx: ApplicationContext,
            ltuid: Option(str, "Mihoyo account ID", autocomplete=get_account_suggestions),
    ):
        mihoyo_id = int(ltuid)
        account = session.get(GenshinUser, (mihoyo_id,))

        if not account:
            await ctx.respond("Account not in the database. Do nothing.")
            return

        if account.discord_id != ctx.author.id:
            await ctx.respond("This ltuid is registered to another discord account.")
            return

        view = UnregisterView(ctx)
        await ctx.respond(
            embed=discord.Embed(
                description=f"This will remove your account {mihoyo_id} from the bot. Are you sure?"
            ),
            view=view,
            ephemeral=True,
        )

        await view.wait()
        if view.value is None:
            await ctx.edit(
                embed=discord.Embed(description=f"Action timed out"), view=None
            )
        elif view.value:
            # Delete all references before removing the main account
            # This assumes we don't have ON DELETE CASCADE as that can be unreliable
            session.execute(delete(UidMapping).where(UidMapping.mihoyo_id == mihoyo_id))
            session.execute(delete(AccountInfo).where(AccountInfo.id == mihoyo_id))
            session.execute(
                delete(GenshinUser).where(GenshinUser.mihoyo_id == mihoyo_id)
            )
            session.commit()
            await ctx.edit(
                embed=discord.Embed(description=f"Account deleted"), view=None
            )
        else:
            await ctx.edit(
                embed=discord.Embed(description=f"Deletion cancelled"), view=None
            )

    @user.command(
        description="To enable or disable certain features",
        guild_ids=guild_level.get_guild_ids(level=3),
    )
    async def settings(self, ctx: ApplicationContext):
        await ctx.defer(ephemeral=True)

        accounts = (
            session.execute(
                select(GenshinUser).where(GenshinUser.discord_id == ctx.author.id)
            ).scalars().all()
        )

        if not accounts:
            await ctx.send_followup(
                "You don't have any registered accounts with this bot."
            )
            return

        for account in accounts:
            gs = account.client
            accounts = await gs.genshin_accounts()
            embed = discord.Embed(
                title=f"Account ({account.mihoyo_id})",
                description=f"The first box is the features you can enable, while the second box will restrict "
                            f"what UIDs the bot can see in your account.\n"
                            f"Hiding a UID may be handy if you don't want it to show up in commands like resin "
                            f"check or resin cap notification.",
            )

            if ctx.guild:
                _guild_level = guild_level.get_guild_level(ctx.guild.id)
            else:
                _guild_level = 3

            await ctx.send_followup(
                embed=embed,
                view=PreferencesView(ctx, account.mihoyo_id, _guild_level, accounts),
                ephemeral=True,
            )

    @retry(
        retry=retry_if_exception_type(genshin.errors.DataNotPublic),
        stop=stop_after_attempt(5),
        wait=wait_fixed(5),
    )
    async def enable_real_time_notes(self, client: genshin.Client, uid: int):
        result = await client.update_settings(
            setting=3, on=True, game=Game.GENSHIN
        )
        logger.info(f"Enabling resin data. Response: {result}")
        await client.get_notes(uid)

    def _validate_discord_user(self, discord_id: int, ltuid: int):
        count = (
            session.execute(
                select(func.count(GenshinUser.mihoyo_id)).where(
                    GenshinUser.discord_id == discord_id, GenshinUser.mihoyo_id != ltuid
                )
            ).scalars().one()
        )

        if count >= 3:
            raise ValidationError(f"You already have a max of {count} accounts")

        return True


@dataclasses.dataclass
class PreferenceOption:
    label: str
    description: str
    value: str
    guild_level: int


ALL_PREFERENCES = [
    PreferenceOption(
        label="Daily checkin",
        description="Auto check-in and notify you",
        value=Preferences.DAILY_CHECKIN,
        guild_level=3,
    ),
    PreferenceOption(
        label="Resin cap",
        description="Send you a message when your resin is capped",
        value=Preferences.RESIN_REMINDER,
        guild_level=2,
    ),
    PreferenceOption(
        label="Expedition completion",
        description="Send you a message when expeditions are done",
        value=Preferences.EXPEDITION_REMINDER,
        guild_level=2,
    ),
    PreferenceOption(
        label="Teapot coin cap",
        description="Send you a message when your teapot coins are capped",
        value=Preferences.TEAPOT_REMINDER,
        guild_level=2,
    ),
    PreferenceOption(
        label="Parametric transformer reminder",
        description="Send you a message when transformer is ready",
        value=Preferences.PARAMETRIC_TRANSFORMER,
        guild_level=2,
    ),
    PreferenceOption(
        label="Auto code redemption",
        description="New codes are auto-redeemed when found",
        value=Preferences.AUTO_REDEEM,
        guild_level=3,
    ),
]


class PreferencesDropdown(discord.ui.Select["Preferences"]):
    def __init__(self, mihoyo_id: int, guild_level: int):
        super().__init__()
        self.mihoyo_id = mihoyo_id
        self.placeholder = "No features enabled"
        self.account = session.get(GenshinUser, (mihoyo_id,))
        self.options = [
            SelectOption(
                label=pref.label,
                description=pref.description,
                value=pref.value,
                default=self.account.settings[pref.value],
            )
            for pref in ALL_PREFERENCES
            if guild_level >= pref.guild_level
        ]

        if not self.account:
            logger.critical("Account might have been deleted")
            raise Exception("Account might have been deleted")

        if not self.options:
            logger.info("Guild level is too low to access settings")
            raise Exception("Guild level is too low to access settings")

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

        await interaction.response.defer()


class UidDropdown(discord.ui.Select["UidSettings"]):
    def __init__(self, mihoyo_id: int, accounts: List[GenshinAccount]):
        super().__init__()
        self.mihoyo_id = mihoyo_id
        self.accounts = accounts
        self.placeholder = "Choose the UIDs you want to use with this bot"
        current_uids = session.execute(
            select(UidMapping.uid).where(UidMapping.mihoyo_id == mihoyo_id)
        ).scalars().all()

        self.options = [
            SelectOption(
                label=str(account.uid),
                description=f"{account.server_name} - {account.nickname} AR{account.level}",
                value=str(account.uid),
                default=account.uid in current_uids,
            )
            for account in self.accounts
        ]

        self.min_values = 0
        self.max_values = len(self.options)

    async def callback(self, interaction: discord.Interaction):
        selected_uids = list(map(int, self.values))
        session.execute(
            delete(UidMapping).where(
                UidMapping.mihoyo_id == self.mihoyo_id,
                UidMapping.uid.not_in(selected_uids),
            )
        )
        session.commit()

        accounts = sorted(
            [account for account in self.accounts if account.uid in selected_uids],
            key=lambda acc: acc.level,
        )
        for uid in selected_uids:
            session.merge(
                UidMapping(
                    uid=uid, mihoyo_id=self.mihoyo_id, main=uid == accounts[-1].uid
                )
            )

        session.commit()

        await interaction.response.defer()


class PreferencesView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext, mihoyo_id: int, guild_level: int,
                 accounts: List[GenshinAccount]):
        super().__init__()
        self.ctx = ctx
        self.add_item(PreferencesDropdown(mihoyo_id, guild_level))
        self.add_item(UidDropdown(mihoyo_id, accounts))

    async def on_timeout(self) -> None:
        """Disables all buttons when the view times out."""
        for item in self.children:
            item.disabled = True
        message = await self.ctx.interaction.original_message()
        await message.edit(view=self)


class UnregisterView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext):
        super().__init__()
        self.ctx = ctx
        self.value = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def confirm(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.value = True
        self.stop()

    async def on_timeout(self) -> None:
        """Disables all buttons when the view times out."""
        for item in self.children:
            item.disabled = True
        message = await self.ctx.interaction.original_message()
        await message.edit(view=self)


class ValidationError(Exception):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg
