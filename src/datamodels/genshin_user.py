import genshin
from sqlalchemy import Integer, String, Column, Text

from datamodels import Base, List


class GenshinUser(Base):
    __tablename__ = 'genshinuser'

    discord_id = Column(Integer, primary_key=True)
    mihoyo_id = Column(Integer, primary_key=True)

    mihoyo_token = Column(String(100))  # for Code redemption, a.k.a. cookie_token
    hoyolab_token = Column(String(100))  # for Hoyolab access, a.k.a. ltoken
    mihoyo_authkey = Column(Text)  # for Wish history

    # A subset of genshin UIDs that belongs to the accounts
    # Useful if user wants to filter out alt UIDs.
    genshin_uids = Column(List)

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
            yield 'ltoken'

        if self.mihoyo_token:
            try:
                await gs.redeem_code("GENSHINGIFT")
            except genshin.errors.InvalidCookies:
                self.mihoyo_token = None
                raise TokenExpiredError("cookie_token is not valid or has expired")
            except Exception:
                pass
            yield 'cookie_token'

        if self.mihoyo_authkey:
            try:
                await gs.transaction_log("primogem", limit=1)
            except genshin.errors.InvalidAuthkey:
                self.mihoyo_authkey = None
                raise TokenExpiredError("authkey is not valid or has expired")
            except Exception:
                pass
            yield 'authkey'

    @property
    def cookies(self) -> dict:
        return {
            'ltuid': self.mihoyo_id,
            'ltoken': self.hoyolab_token,
            'account_id': self.mihoyo_id,
            'cookie_token': self.mihoyo_token,
        }

    @property
    def client(self) -> genshin.GenshinClient:
        return genshin.GenshinClient(cookies=self.cookies, authkey=self.mihoyo_authkey)


class TokenExpiredError(Exception):
    pass
