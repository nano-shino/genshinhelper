from sqlalchemy import Integer, String, Column

from datamodels import Base


class GenshinUser(Base):
    __tablename__ = 'genshin_user'

    discord_id = Column(Integer, primary_key=True)
    mihoyo_id = Column(Integer, primary_key=True)
    mihoyo_token = Column(String(100))
    hoyolab_token = Column(String(100))
    genshin_uid = Column(Integer)
