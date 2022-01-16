from sqlalchemy import Integer, Column, DateTime, Identity

from datamodels import Base, Jsonizable


class SpiralAbyssRotation(Base):
    __tablename__ = "abyssrotation"

    id = Column(Integer, Identity(), primary_key=True)
    start = Column(DateTime, nullable=False, index=True)
    end = Column(DateTime, nullable=False, index=True)
    data = Column(Jsonizable)
