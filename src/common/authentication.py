from sqlalchemy import select

from common.db import session
from datamodels.uid_mapping import UidMapping


def own_uid(discord_id: int, uid: int):
    mappings = session.execute(
        select(UidMapping).join(UidMapping.genshin_user).where(UidMapping.uid == uid)).scalars().all()

    if len(mappings) != 1:
        return False

    mapping = mappings[0]

    return mapping.genshin_user.discord_id == discord_id
