import asyncio
import json
import re
from typing import Iterable, List

import aiohttp
import discord
import genshin.errors
from discord.ext import commands, tasks
from lxml import html
from sqlalchemy import select

from common import conf
from common.constants import Preferences
from common.db import session
from common.logging import logger
from datamodels.code_redemption import RedeemableCode
from datamodels.genshin_user import GenshinUser
from datamodels.guild_settings import GuildSettings, GuildSettingKey


CODE_REGEX = r"^[A-Za-z0-9]{9,20}$"
ENNEAD_URL = "https://api.ennead.cc/codes/genshin"
INACTIVE_SECTION_REGEX = re.compile(r"expired|invalid|redeemed|inactive", re.IGNORECASE)


def parse_pockettactics_codes(page: str) -> List[str]:
    """
    Extracts active codes from the Pocket Tactics codes article.

    Codes are the bold text of list items under the article body. Codes are skipped
    when they are struck through, sit in a list item that says it is expired, or sit
    under a heading that marks the section as expired/invalid.
    """
    tree = html.fromstring(page)
    content_div = tree.xpath('//div[@class="entry-content"]')
    if not content_div:
        logger.warning("Pocket Tactics codes page has no entry-content")
        return []

    codes = []
    for ul in content_div[0].xpath('.//ul'):
        heading = ul.xpath('preceding::*[self::h1 or self::h2 or self::h3 or self::h4][1]')
        if heading and INACTIVE_SECTION_REGEX.search(heading[0].text_content()):
            continue

        for item in ul.xpath('./li'):
            if INACTIVE_SECTION_REGEX.search(item.text_content()):
                continue
            for strong in item.xpath('./strong[not(ancestor::s or ancestor::del or ancestor::strike)]'):
                code = strong.text_content().strip()
                if looks_like_code(code) and code not in codes:
                    codes.append(code)
    return codes


def looks_like_code(text: str) -> bool:
    """
    Bold words in articles (e.g. "Primogems") also match CODE_REGEX. Codes always
    have a digit, an uppercase letter after the first character, or are all caps.
    """
    if not re.match(CODE_REGEX, text):
        return False
    return any(c.isdigit() for c in text) or any(c.isupper() for c in text[1:]) or text.isupper()


class GenshinCodeScanner(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.start_up = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.start_up:
            self.poll.start()
            self.start_up = True

    @tasks.loop(minutes=5)
    async def poll(self):
        async with aiohttp.ClientSession() as http:
            codes = set()
            try:
                codes.update(await self.get_codes_from_ennead(http))
            except Exception:
                logger.exception("Cannot fetch codes from Ennead, falling back to Pocket Tactics")

            if not codes:
                codes.update([c async for c in self.get_codes_from_pockettactics()])

            for page in conf.CODE_URL:
                async with http.get(page) as response:
                    data = await response.read()
                    for potential_code in self.get_codes_from_text(data.decode("utf-8")):
                        code = potential_code.strip()
                        if re.match(CODE_REGEX, code):
                            codes.add(code)

        existing_codes = set(
            session.execute(select(RedeemableCode.code)).scalars()
        )

        if codes.issubset(existing_codes):
            return

        logger.info(f"New code is available: {codes}")

        new_codes = codes - existing_codes

        for code in new_codes:
            session.merge(RedeemableCode(code=code, working=True))

        for code in existing_codes - codes:
            session.merge(RedeemableCode(code=code, working=False))

        session.commit()

        await self.send_notification(new_codes)
        await self.redeem(new_codes)

    async def send_notification(self, codes: Iterable[str]):
        embed = discord.Embed(
            title="New codes available",
            description="\n".join(
                f"[{code}](https://genshin.hoyoverse.com/en/gift?code={code})"
                for code in codes
            )
        )

        for code_channel in session.execute(
                select(GuildSettings).where(
                    GuildSettings.key == GuildSettingKey.CODE_CHANNEL
                )
        ).scalars():
            try:
                channel = await self.bot.fetch_channel(code_channel.value)
                code_role = session.get(
                    GuildSettings,
                    (code_channel.guild_id, GuildSettingKey.CODE_ROLE),
                )
                await channel.send(
                    content=f"\n<@&{code_role.value}>" if code_role else None,
                    embed=embed,
                )
            except Exception:
                logger.exception("Cannot send new code notifications")

    async def redeem(self, codes: Iterable[str]):
        accounts: List[GenshinUser] = (
            session.execute(
                select(GenshinUser).where(GenshinUser.mihoyo_token.is_not(None))
            ).scalars().all()
        )

        for code in codes:
            queue = []
            for account in accounts:
                if not account.settings[Preferences.AUTO_REDEEM]:
                    continue
                logger.info(f"Redeeming code {code} for account {account.mihoyo_id}")
                queue.append(asyncio.create_task(account.client.redeem_code(code=code)))

            results = await asyncio.gather(*queue, return_exceptions=True)

            if results and isinstance(results[0], genshin.errors.RedemptionInvalid):
                session.merge(RedeemableCode(code=code, working=False))
                logger.info(f"Code {code} expired. Updating database")

            logger.info(results)
            await asyncio.sleep(5)

        session.commit()

    async def get_codes_from_ennead(self, http: aiohttp.ClientSession):
        async with http.get(ENNEAD_URL) as response:
            response.raise_for_status()
            return {
                item["code"] for item in await response.json()
                if re.match(CODE_REGEX, item["code"])
            }

    async def get_codes_from_pockettactics(self):
        async with aiohttp.ClientSession() as session:
            url = "https://www.pockettactics.com/genshin-impact/codes"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
            async with session.get(url, headers=headers) as r:
                if r.status != 200:
                    logger.warning(f"Cannot fetch Pocket Tactics codes: HTTP {r.status}")
                    return

                for code in parse_pockettactics_codes(await r.text()):
                    yield code

    def get_codes_from_text(self, data):
        """
        Supports extracting codes from the following format:
         - Line-by-line codes
         - JSON (from https://ataraxyaffliction.github.io/)
        """
        def parse_json(obj):
            return {item["code"] for item in obj}

        def parse_text(data):
            codes = set()
            for line in data.splitlines():
                code = line.strip()
                if re.match(CODE_REGEX, code):
                    codes.add(code)
            return codes

        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            return parse_text(data)
        else:
            return parse_json(obj)
