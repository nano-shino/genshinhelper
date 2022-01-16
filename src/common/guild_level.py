"""
Depending on the guild level (1-5), we expose certain commands. The higher the guild level, the more commands it has.
"""
import os
from typing import List


def _get_env_var(key: str):
    return [int(x) for x in (os.getenv(key) or "").split(",") if x]


MAX_LEVEL = 5
GUILD_IDS = {i: _get_env_var(f"LEVEL_{i}_GUILDS") for i in range(1, MAX_LEVEL + 1)}


def get_guild_ids(level: int) -> List[int]:
    """
    Returns a list of guild ids for a command level. To be used in the decorator like so:

    @slash_command(
        guild_ids=get_guild_ids(level=5)
    )

    :param level: The level of the command. Higher = more privilege.
    :return:
    """
    guild_ids = []
    for i in range(level, MAX_LEVEL + 1):
        guild_ids += GUILD_IDS[i]
    return guild_ids


def get_guild_level(guild_id: int) -> int:
    """
    Determines a guild level based on a guild id.

    :param guild_id: Discord guild id.
    :return: The guild level
    """
    for i in range(MAX_LEVEL, 0, -1):
        if guild_id in GUILD_IDS[i]:
            return i
    return 0
