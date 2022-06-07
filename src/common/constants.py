from datetime import timedelta


class Emoji:
    CHECK = ":white_check_mark:"
    CROSS = ":x:"
    LOADING = "<a:loading:926460289388515360>"


class Time:
    PARAMETRIC_TRANSFORMER_COOLDOWN = timedelta(days=6, hours=22)


class Preferences:
    DAILY_CHECKIN = "daily_checkin"
    RESIN_REMINDER = "resin_reminder"
    EXPEDITION_REMINDER = "expedition_reminder"
    TEAPOT_REMINDER = "teapot_reminder"
    PARAMETRIC_TRANSFORMER = "parametric"
    AUTO_REDEEM = "auto_redeem"


DEFAULT_SETTINGS = {
    Preferences.DAILY_CHECKIN: True,
    Preferences.RESIN_REMINDER: True,
    Preferences.EXPEDITION_REMINDER: False,
    Preferences.TEAPOT_REMINDER: True,
    Preferences.PARAMETRIC_TRANSFORMER: True,
    Preferences.AUTO_REDEEM: True,
}
