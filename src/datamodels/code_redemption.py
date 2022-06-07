from sqlalchemy import Column, String, Boolean

from datamodels import Base


class RedeemableCode(Base):
    __tablename__ = "codes"

    code = Column(String, primary_key=True)
    working = Column(Boolean, nullable=False, default=True)
