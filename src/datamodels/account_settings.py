from sqlalchemy import Integer, Column, ForeignKey

from datamodels import Base, Jsonizable
from datamodels.genshin_user import GenshinUser


class AccountInfo(Base):
    __tablename__ = "accountinfo"

    id = Column(
        Integer, ForeignKey(GenshinUser.mihoyo_id, ondelete="CASCADE"), primary_key=True
    )
    settings = Column(Jsonizable)


class Preferences:
    DAILY_CHECKIN = "daily_checkin"
    RESIN_REMINDER = "resin_reminder"
    PARAMETRIC_TRANSFORMER = "parametric"


DEFAULT_SETTINGS = {
    Preferences.DAILY_CHECKIN: False,
    Preferences.RESIN_REMINDER: True,
    Preferences.PARAMETRIC_TRANSFORMER: True,
}
