from dateutil.relativedelta import relativedelta


class Emoji:
    CHECK = ":white_check_mark:"
    CROSS = ":x:"
    LOADING = "<a:loading:926460289388515360>"


class Time:
    PARAMETRIC_TRANSFORMER_COOLDOWN = relativedelta(days=6, hours=22)
