import asyncio

from discord.utils import Values, AutocompleteFunc, AutocompleteContext, V
from thefuzz import process


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

        matches = process.extract(
            (ctx.value or "").lower(), list(map(str.lower, _values)),
            limit=25)
        return (val for val, score in matches if score >= threshold)

    return autocomplete_callback
