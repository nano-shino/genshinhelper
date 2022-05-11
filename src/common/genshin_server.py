import dataclasses
from datetime import timezone, timedelta, time, datetime

import genshin
from dateutil.relativedelta import relativedelta

utc_offset = lambda hour_offset: timezone(timedelta(seconds=hour_offset * 3600))

# This applies to all regions.
SERVER_RESET_TIME = time(hour=4)


@dataclasses.dataclass
class Server:
    region: str
    tzoffset: timezone

    @property
    def current_time(self):
        return datetime.now(tz=self.tzoffset)

    @property
    def last_daily_reset(self):
        reset_time = datetime.combine(self.current_time, SERVER_RESET_TIME).replace(
            tzinfo=self.tzoffset
        )
        if reset_time > self.current_time:
            reset_time -= relativedelta(days=1)
        return reset_time

    @property
    def last_weekly_reset(self):
        return self.last_daily_reset - timedelta(days=self.last_daily_reset.weekday())

    @property
    def day_beginning(self):
        return datetime.combine(self.current_time, time()).replace(tzinfo=self.tzoffset)


class ServerEnum:
    NORTH_AMERICA = Server("os_usa", utc_offset(-5))
    ASIA = Server("os_asia", utc_offset(+8))
    EUROPE = Server("os_euro", utc_offset(+1))

    @staticmethod
    def from_uid(uid: int):
        region = genshin.utility.recognize_genshin_server(uid)
        for e in ServerEnum.__dict__.values():
            if isinstance(e, Server) and e.region == region:
                return e
