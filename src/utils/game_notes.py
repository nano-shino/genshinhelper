import asyncio

import genshin


async def get_notes(gs: genshin.Client, uid: int) -> dict:
    raw_notes = None
    for _ in range(5):
        raw_notes = await gs._GenshinBattleChronicleClient__get_genshin("dailyNote", uid, cache=False)
        if raw_notes['transformer']:
            return raw_notes
        await asyncio.sleep(0.5)
    return raw_notes
