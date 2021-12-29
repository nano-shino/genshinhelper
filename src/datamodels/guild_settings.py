from sqlalchemy import Integer, Column, Text, String

from datamodels import Base


class GuildSettings(Base):
    __tablename__ = 'guildsettings'

    guild_id = Column(Integer, primary_key=True)
    key = Column(String(100), primary_key=True)
    value = Column(Text)
