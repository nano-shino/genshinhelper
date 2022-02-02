from sqlalchemy import Integer, Column, ForeignKey

from datamodels import Base, Jsonizable
from datamodels.genshin_user import GenshinUser


class AccountInfo(Base):
    __tablename__ = "accountinfo"

    id = Column(
        Integer, ForeignKey(GenshinUser.mihoyo_id, ondelete="CASCADE"), primary_key=True
    )
    settings = Column(Jsonizable)
