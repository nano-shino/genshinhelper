from sqlalchemy import Integer, Column, Text, String

from datamodels import Base


class GuildSettings(Base):
    __tablename__ = "guildsettings"

    guild_id = Column(Integer, primary_key=True)
    key = Column(String(100), primary_key=True)
    value = Column(Text)


class GuildSettingKey:
    COMMAND_PREFIX = "command_prefix"
    EVENT_CHANNEL = "event_channel"
    EVENT_ROLE = "event_role"
    CODE_CHANNEL = "code_channel"
    CODE_ROLE = "code_role"
    BOT_CHANNEL = "bot_channel"
    SELF_ASSIGNABLE_ROLES = "self_assignable_roles"


ALL_KEYS = {k: v for k, v in GuildSettingKey.__dict__.items() if not k.startswith("_")}
