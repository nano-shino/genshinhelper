import datetime
import enum

from sqlalchemy import Integer, Column, String, Identity, ForeignKey
from sqlalchemy.orm import relationship

from common.genshin_server import ServerEnum
from datamodels import Base


class DiaryAction(Base):
    __tablename__ = "diaryactions"

    id = Column(Integer, Identity(), primary_key=True)
    uid = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    type = Column(Integer, nullable=False)
    action_id = Column(Integer, nullable=False)
    action = Column(String(100), nullable=False)
    timestamp = Column(Integer, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    span_id = Column(
        Integer, ForeignKey("_diaryactionspan.id", ondelete="CASCADE"), nullable=False
    )
    span = relationship("DiaryActionSpan")

    @property
    def time(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(
            self.timestamp, tz=ServerEnum.from_uid(self.uid).tzoffset
        )


class DiaryActionSpan(Base):
    __tablename__ = "_diaryactionspan"

    id = Column(Integer, Identity(), primary_key=True)
    start_ts = Column(Integer, nullable=False)
    end_ts = Column(Integer, nullable=False)


class DiaryType(enum.Enum):
    PRIMOGEM = 1
    MORA = 2


class MoraActionId:
    # Daily Commission Rewards
    COMMISSION_LIYUE = 27
    COMMISSION_INAZUMA = 33
    DAILY_COMMISSION_BONUS = 26

    # Expedition Reward
    EXPEDITION_REWARD = 29

    # Reward From Defeating Monsters
    DEFEATING_MONSTERS = 37

    # Reward From Defeating the BOSS
    WEEKLY_BOSS = 52

    # Domain Clear Reward
    DOMAIN_CLEAR = 1016

    # Ley Line Blossom Reward
    MORA_LEYLINE = 55

    # Random Event Reward
    RANDOM_EVENT_LIYUE = 28
    RANDOM_EVENT_INAZUMA = 32

    # Destroying Items
    DESTROY_ARTIFACTS = 1052

    # Quests
    WORLD_QUEST = 2
    REPUTATION_QUEST = 80

    # Domain First Clear Reward
    DOMAIN_FIRST_CLEAR = 20

    # Treasure Chest Rewards
    CHEST = 39

    # Reputation Level Reward
    REPUTATION_LEVEL_20K = 81
    REPUTATION_LEVEL_50K = 82

    # Spiral Abyss Rewards
    SPIRAL_ABYSS_CHAMBER_PROGRESSION = 49
    SPIRAL_ABYSS_CHAMBER_STAR = 48

    # In-Game Mail Rewards
    INGAME_MAIL = 12

    # Event Rewards
    EVENT = 67
    EVENT_2 = 101
    PARAMETRIC_TRANSFORMER = 1074
    EVENT_4 = 1117

    # Other
    # UNKNOWN = 1100
    REPUTATION_BOUNTY = 1054
    # UNKNOWN = 2
    FERRET = 42


class MoraAction:
    DAILY_COMMISSIONS = "Daily Commission Rewards"
    DESTROYING_ARTIFACTS = "Destroying Items"
    DOMAIN_CLEAR = "Domain Clear Reward"
    DOMAIN_FIRST_CLEAR = "Domain First Clear Reward"
    EVENT = "Event Rewards"
    EXPEDITION = "Expedition Reward"
    IN_GAME_MAIL = "In-Game Mail Rewards"
    KILLING_BOSS = "Reward From Defeating the BOSS"
    KILLING_MONSTER = "Reward From Defeating Monsters"
    LEY_LINE = "Ley Line Blossom Reward"
    OTHER = "OTHER"
    QUESTS = "Quests"
    RANDOM_EVENT = "Random Event Reward"
    REPUTATION_LEVEL = "Reputation Level Reward"
    SPIRAL_ABYSS = "Spiral Abyss Rewards"
    TREASURE_CHEST = "Treasure Chest Rewards"
