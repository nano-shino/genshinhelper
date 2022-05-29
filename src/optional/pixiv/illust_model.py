from sqlalchemy import Integer, Column, ForeignKey

from datamodels import Base


class Illust(Base):
    __tablename__ = "pixiv_illust"

    id = Column(
        Integer, primary_key=True
    )
