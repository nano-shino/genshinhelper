import asyncio
import itertools

from discord.utils import Values, AutocompleteFunc, AutocompleteContext, V
from rapidfuzz import process


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
