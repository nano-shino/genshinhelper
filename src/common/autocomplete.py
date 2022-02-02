import asyncio
import itertools

from discord.utils import Values, AutocompleteFunc, AutocompleteContext, V
from rapidfuzz import process
from sqlalchemy import select

from common.db import session
from datamodels.genshin_user import GenshinUser
from datamodels.uid_mapping import UidMapping


def fuzzy_autocomplete(values: Values, threshold: int = 50) -> AutocompleteFunc:
    """
    Levenshtein matching allowing for small typos.

    :param values: Possible values for the option.
        Accepts an iterable of :class:`str`, a callable (sync or async) that takes a single argument of
        :class:`AutocompleteContext`, or a coroutine. Must resolve to an iterable of :class:`str`.
    :param threshold: Lowest matching threshold.
    :return: A wrapped callback for the autocomplete.
    """

    async def autocomplete_callback(ctx: AutocompleteContext) -> V:
        _values = values  # since we reassign later, python considers it local if we don't do this

        if callable(_values):
            _values = _values(ctx)
        if asyncio.iscoroutine(_values):
            _values = await _values

        if not ctx.value:
            return iter(itertools.islice(_values, 25))

        # lookup to reverse case-lowering
        lower_dict = {val.lower(): val for val in _values}
        matches = process.extract(ctx.value.lower(), list(lower_dict.keys()), limit=25)
        return (lower_dict[val] for val, score, idx in matches if score >= threshold)

    return autocomplete_callback


def get_account_suggestions(ctx: AutocompleteContext):
    ltuid_matches = []
    discord_id = ctx.interaction.user.id
    for account in session.execute(
        select(GenshinUser).where(GenshinUser.discord_id == discord_id)
    ).scalars():
        if not ctx.value or str(account.mihoyo_id).startswith(str(ctx.value)):
            ltuid_matches.append(str(account.mihoyo_id))
    return ltuid_matches


def get_uid_suggestions(ctx: AutocompleteContext):
    uid_matches = []
    discord_id = ctx.interaction.user.id
    for uidmapping in session.execute(
            select(UidMapping).join(UidMapping.genshin_user).where(GenshinUser.discord_id == discord_id)
    ).scalars():
        if not ctx.value or str(uidmapping.uid).startswith(str(ctx.value)):
            uid_matches.append(str(uidmapping.uid))
    return uid_matches
