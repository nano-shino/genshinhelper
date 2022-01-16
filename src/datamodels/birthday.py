from sqlalchemy import Integer, Column, Text, DateTime

from datamodels import Base


class Birthday(Base):
    __tablename__ = "bday"

    discord_id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, primary_key=True)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    timezone = Column(Text, nullable=False)
    reminded_at = Column(DateTime)  # UTC timezone
