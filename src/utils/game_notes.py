import asyncio

import genshin

from common.logging import logger

__cache = genshin.Cache(maxsize=256, ttl=10)


async def get_notes(gs: genshin.Client, uid: int) -> dict:
    # The reason we have this utility method to get notes instead of using client.get_genshin_notes
    # is because the API sometimes returns empty teapot/transformer data.
    # One way to deal with this is to retry (max 5 times) until we see transformer data. Through
    # observation, teapot data is also available when transformer data is available.
    data = await __cache.get(uid)

    if data:
        return data

    # Call API with retries
    for _ in range(5):
        logger.info(f"Getting real-time notes for {uid}")
        data = await gs._request_genshin_record("dailyNote", uid, cache=False)
        if data['transformer']:
            break
        await asyncio.sleep(0.5)

    await __cache.set(uid, data)

    return data
