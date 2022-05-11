import json
from json import JSONDecodeError
from typing import List

import discord
from discord.ext import commands

from common import guild_level
from common.db import session
from common.logging import logger
from datamodels.guild_settings import GuildSettings, GuildSettingKey


class Dropdown(discord.ui.Select):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(
            placeholder="Choose your roles...",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        new_roles = [
            interaction.guild.get_role(int(role_id)) for role_id in self.values
        ]
        old_roles = [
            interaction.guild.get_role(int(opt.value))
            for opt in self.options
            if opt.value not in self.values
        ]
        try:
            if new_roles:
                await interaction.user.add_roles(
                    *new_roles, reason="User assigned their own roles"
                )
            if old_roles:
                await interaction.user.remove_roles(
                    *old_roles, reason="User removed their own roles"
                )
            await interaction.response.defer()
        except discord.Forbidden:
            await interaction.response.send_message(
                "Bot doesn't have permission to manage roles or the roles are higher than the bot's role"
            )


class DropdownView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext, options: List[discord.SelectOption]):
        super().__init__()
        self.ctx = ctx
        self.add_item(Dropdown(options))

    async def on_timeout(self) -> None:
        """Disables all buttons when the view times out."""
        for item in self.children:
            item.disabled = True
        message = await self.ctx.interaction.original_message()
        await message.edit(view=self)


class RoleManager(commands.Cog):
    def __init__(self, bot: discord.Bot = None):
        self.bot = bot

    @commands.slash_command(
        description="Get your own roles", guild_ids=guild_level.get_guild_ids(level=3)
    )
    async def roles(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        options = []
        roles = session.get(
            GuildSettings, (ctx.guild_id, GuildSettingKey.SELF_ASSIGNABLE_ROLES)
        )

        if not roles:
            await ctx.respond("This server does not have any self-assignable roles")
            return

        try:
            roles = json.loads(roles.value)
        except JSONDecodeError:
            logger.exception("Can't decode json")
            await ctx.respond("Mis-configured roles. Talk to your server owner")
            return

        try:
            for role_id in roles:
                role = ctx.guild.get_role(int(role_id))
                member_role = ctx.author.get_role(int(role_id))
                options.append(
                    discord.SelectOption(
                        label=role.name,
                        description=roles[role_id],
                        value=role_id,
                        default=bool(member_role),
                    )
                )
        except Exception:
            await ctx.respond("Mis-configured roles. Talk to your server owner")
            logger.exception("Role does not exist")
            return

        await ctx.respond("Choose the roles you want:", view=DropdownView(ctx, options))
