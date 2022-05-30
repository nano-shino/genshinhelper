from sqlalchemy import Integer, Column, String, Boolean, DateTime

from datamodels import Base, Jsonizable


class ScheduledItem(Base):
    """
    A generic table to schedule reminders or tasks.
    The column type indicates what it is.

    For example, a UID may have a resin_cap reminder, or a daily checkin task.

    If the task is done or the reminder is sent, we can mark `done=True`.
    """

    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True)
    type = Column(String(100), primary_key=True)
    scheduled_at = Column(
        DateTime, nullable=False, index=True
    )  # unless otherwise specified, this should be in UTC
    done = Column(Boolean, nullable=False, default=False)
    context = Column(Jsonizable)


class ItemType:
    DAILY_CHECKIN = "checkin"
    RESIN_CAP = "resin-cap"
    EXPEDITION_CAP = "expedition-cap"
    TEAPOT_CAP = "teapot-cap"
    PARAMETRIC_TRANSFORMER = "parametric"
