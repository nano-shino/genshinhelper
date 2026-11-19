import discord

from common.db import session
from common.logging import logger
from datamodels.genshin_user import GenshinUser

LTOKEN = "ltoken"
COOKIE_TOKEN = "cookie_token"

_TOKEN_ATTRS = {
    LTOKEN: "hoyolab_token",
    COOKIE_TOKEN: "mihoyo_token",
}


async def expire_token(bot: discord.Bot, account: GenshinUser, token: str = LTOKEN):
    """
    Clears an expired token and tells the user once. The account itself is kept; clearing the
    ltoken makes it inactive (GenshinUser.is_active) so background jobs stop processing it until
    the user registers again.
    """
    attr = _TOKEN_ATTRS[token]
    if not getattr(account, attr):
        return  # already expired and notified

    setattr(account, attr, None)
    session.merge(account)
    session.commit()
    logger.info(f"Cleared expired {token} for Hoyolab ID {account.mihoyo_id}")

    try:
        discord_user = await bot.fetch_user(account.discord_id)
        channel = await discord_user.create_dm()
        await channel.send(
            embed=discord.Embed(
                title=":warning: Account Access Failure",
                description=f"HoYoLAB rejected your {token} for Hoyolab ID {account.mihoyo_id}.\n"
                            f"It may have expired, been invalidated by a password change or logout, "
                            f"or been registered without ltmid_v2.\n"
                            f"Please register again with `/user register` if you want to continue using the bot."
            )
        )
    except Exception:
        logger.exception(f"Cannot notify {account.discord_id} about expired {token}")
