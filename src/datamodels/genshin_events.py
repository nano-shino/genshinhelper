from sqlalchemy import Column, String, Text, DateTime, Integer

from datamodels import Base


class GenshinEvent(Base):
    __tablename__ = "genshinevents"

    id = Column(String(100), primary_key=True)
    type = Column(String(100))
    description = Column(Text)
    url = Column(Text, nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)


class EventSource(Base):
    __tablename__ = "eventsource"

    channel_id = Column(Integer, primary_key=True)
    read_until = Column(DateTime)
