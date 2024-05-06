import json
from typing import Dict, Any, List, Optional

import genshin
from sqlalchemy import Integer, String, Column, Text
from sqlalchemy.orm import relationship

import common.constants
from datamodels import Base


class GenshinUser(Base):
    __tablename__ = "genshinuser"

    mihoyo_id = Column(Integer, primary_key=True)
    discord_id = Column(Integer, nullable=False, index=True)

    mihoyo_token = Column(String(100))  # for Code redemption, a.k.a. cookie_token
    hoyolab_token = Column(String(100))  # for Hoyolab access, a.k.a. ltoken
    mihoyo_authkey = Column(Text)  # for Wish history

    # Associated UIDs
    # Useful if user wants to filter out alt accounts
    uid_mappings = relationship("UidMapping", backref="genshin_user")

    # Settings for this account
    info = relationship("AccountInfo", backref="genshin_user", uselist=False)

    async def validate(self):
        gs = self.client

        if self.hoyolab_token:
            try:
                await gs.get_reward_info()
            except genshin.errors.InvalidCookies:
                self.hoyolab_token = None
                raise TokenExpiredError("ltoken is not valid or has expired")
            except Exception:
                pass
            yield "ltoken"

        if self.mihoyo_token:
            try:
                await gs.redeem_code("GENSHIN123")  # Using a random code to validate cookies
            except genshin.errors.InvalidCookies:
                self.mihoyo_token = None
                raise TokenExpiredError("cookie_token is not valid or has expired")
            except Exception:
                pass
            yield "cookie_token"

        if self.mihoyo_authkey:
            try:
                await gs.transaction_log("primogem", limit=1)
            except genshin.errors.InvalidAuthkey:
                self.mihoyo_authkey = None
                raise TokenExpiredError("authkey is not valid or has expired")
            except Exception:
                pass
            yield "authkey"

    @property
    def cookies(self) -> dict:
        base = {
            "ltuid": self.mihoyo_id,
            "ltuid_v2": self.mihoyo_id,
            "account_id": self.mihoyo_id,
            "account_id_v2": self.mihoyo_id,
        }

        if self.hoyolab_token:
            if self.hoyolab_token.startswith("v2_"):
                base["ltoken_v2"] = self.hoyolab_token
            elif self.hoyolab_token.startswith("{"):
                base.update(json.loads(self.hoyolab_token))
        elif self.hoyolab_token:
            base["ltoken"] = self.hoyolab_token

        if self.mihoyo_token and self.mihoyo_token.startswith("v2_"):
            base["cookie_token_v2"] = self.mihoyo_token
        elif self.mihoyo_token:
            base["cookie_token"] = self.mihoyo_token

        return base

    @property
    def client(self) -> genshin.Client:
        client = genshin.Client(cookies=self.cookies, authkey=self.mihoyo_authkey)
        if self.main_genshin_uid:
            client.uid = self.main_genshin_uid
        return client

    @property
    def settings(self) -> Dict[str, Any]:
        if self.info:
            return common.constants.DEFAULT_SETTINGS | self.info.settings
        return common.constants.DEFAULT_SETTINGS

    @property
    def genshin_uids(self) -> List[int]:
        return [mapping.uid for mapping in self.uid_mappings]

    @property
    def main_genshin_uid(self) -> Optional[int]:
        for mapping in self.uid_mappings:
            if mapping.main:
                return mapping.uid


class TokenExpiredError(Exception):
    pass
