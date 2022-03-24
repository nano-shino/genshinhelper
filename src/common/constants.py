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
    TEAPOT_REMINDER = "teapot_reminder"
    PARAMETRIC_TRANSFORMER = "parametric"


DEFAULT_SETTINGS = {
    Preferences.DAILY_CHECKIN: True,
    Preferences.RESIN_REMINDER: True,
    Preferences.TEAPOT_REMINDER: False,
    Preferences.PARAMETRIC_TRANSFORMER: True,
}