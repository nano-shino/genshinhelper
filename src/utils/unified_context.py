from typing import Union, Optional

import discord
from discord.ext import commands


def _remove_incompatible_keywords(kwargs):
    new_dict = {}
    for k in kwargs:
        if k in ["ephemeral"]:
            continue
        new_dict[k] = kwargs[k]
    return new_dict


class UnifiedContext:
    """
    This class allows the command handler to interact with ctx of the legacy form in the same way as slash command ctx.
    """

    def __init__(self, orig_ctx: Union[commands.Context, discord.ApplicationContext]):
        self._orig_ctx = orig_ctx
        self.is_application_command = isinstance(orig_ctx, discord.ApplicationContext)
        self.author = self._orig_ctx.author
        self.guild = self._orig_ctx.guild
        self.channel = self._orig_ctx.channel
        self._orig_message: Optional[discord.Message] = None

    async def defer(self, **kwargs):
        if self.is_application_command:
            await self._orig_ctx.defer(**kwargs)

    async def original_message(self) -> Union[discord.InteractionMessage, discord.Message]:
        if self.is_application_command:
            return await self._orig_ctx.interaction.original_message()
        return self._orig_message

    async def send_followup(self, *args, **kwargs):
        if self.is_application_command:
            await self._orig_ctx.send_followup(*args, **kwargs)
        else:
            self._orig_message = await self._orig_ctx.send(
                *args, **_remove_incompatible_keywords(kwargs)
            )

    async def respond(self, *args, **kwargs):
        if self.is_application_command:
            await self._orig_ctx.respond(*args, **kwargs)
        else:
            self._orig_message = await self._orig_ctx.send(
                *args, **_remove_incompatible_keywords(kwargs)
            )

    async def edit(self, *args, **kwargs):
        if self.is_application_command:
            await self._orig_ctx.edit(*args, **kwargs)
        else:
            if self._orig_message:
                await self._orig_message.edit(
                    *args, **_remove_incompatible_keywords(kwargs)
                )
            else:
                self._orig_message = await self._orig_ctx.send(
                    *args, **_remove_incompatible_keywords(kwargs)
                )
