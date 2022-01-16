from sqlalchemy import Integer, Column, Boolean, ForeignKey

from datamodels import Base


class UidMapping(Base):
    __tablename__ = "uidmapping"

    uid = Column(Integer, primary_key=True)
    mihoyo_id = Column(
        Integer, ForeignKey("genshinuser.mihoyo_id", ondelete="CASCADE"), nullable=False
    )
    main = Column(Boolean, nullable=False, default=False)
