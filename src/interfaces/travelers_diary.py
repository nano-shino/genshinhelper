import asyncio
from collections import defaultdict
from datetime import datetime
from typing import List

import dateutil.parser
import genshin
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from tenacity import retry, wait_exponential, stop_after_attempt

from common.db import session
from common.genshin_server import ServerEnum
from common.logging import logger
from datamodels.diary_action import DiaryAction, DiaryActionSpan, DiaryType
from utils.ledger import merge_time_series, trim_right, copy_action

locks = defaultdict(lambda: asyncio.Lock())


class TravelersDiary:
    PAGE_LIMIT = 20  # This is a fixed value in Mihoyo API. Don't change it.

    def __init__(self, client: genshin.Client, uid: int):
        self.client = client
        self.uid = uid
        self.server = ServerEnum.from_uid(self.uid)

    def get_logs(
            self, diary_type: DiaryType, start_time: datetime, end_time: datetime = None
    ) -> List[DiaryAction]:
        """
        Retrieves logs from local database. If data was not fetched before, then it won't return
        anything.

        :param diary_type: Mora or primogem diary.
        :param start_time: The earliest time you want of the logs.
        :param end_time: The latest time you want of the logs.
        :return: A list of diary actions.
        """
        end_time = end_time or datetime.now(tz=self.server.tzoffset)

        return (
            session.execute(
                select(DiaryAction).where(
                    DiaryAction.type == diary_type.value,
                    DiaryAction.uid == self.uid,
                    DiaryAction.timestamp >= start_time.timestamp(),
                    DiaryAction.timestamp < end_time.timestamp(),
                )
            )
                .scalars()
                .all()
        )

    async def fetch_logs(
            self, diary_type: DiaryType, start_time: datetime, end_time: datetime = None
    ) -> List[DiaryAction]:
        """
        This is a highly-complicated function, but it's basically trying to fetch the diary logs
        from Mihoyo servers and cache the data to avoid hammering the servers.

        For example, if we fetch day 1, and then day 3. Then day 1 and day 3 will be saved to the
        database. Now if we fetch days 1-4, the function will only need to fetch day 2 and 4.

        :param diary_type: Mora or primogem diary.
        :param start_time: The earliest time you want of the logs.
        :param end_time: The latest time you want of the logs.
        :return: A list of diary actions.
        """
        end_time = end_time or datetime.now(tz=self.server.tzoffset)

        if start_time > end_time:
            raise ValueError("start_time is after end_time")

        logger.info(f"Get logs for start_time={start_time} and end_time={end_time}")

        # Number of months that we need to look up
        end_marker = datetime(
            year=end_time.year, month=end_time.month, day=1, tzinfo=end_time.tzinfo
        )

        uid_lock = locks[self.uid]

        if uid_lock.locked():
            logger.info(
                f"Another fetch for UID-{self.uid} is ongoing. Waiting for lock..."
            )

        await uid_lock.acquire()

        try:
            await self._fetch_logs(diary_type, start_time, end_marker)
        finally:
            uid_lock.release()

        return self.get_logs(diary_type, start_time, end_time)

    async def _fetch_logs(self, diary_type: DiaryType, start_time: datetime, end_marker: datetime):
        while end_marker.year > start_time.year or (
                end_marker.year == start_time.year and end_marker.month >= start_time.month
        ):
            month = end_marker.month
            year = end_marker.year
            end_marker -= relativedelta(months=1)
            stored = (
                session.execute(
                    select(DiaryAction).where(
                        DiaryAction.type == diary_type.value,
                        DiaryAction.uid == self.uid,
                        DiaryAction.month == month,
                        DiaryAction.year == year,
                    ).order_by(DiaryAction.timestamp.desc())
                ).scalars().all()
            )

            actions = []
            month_end = False
            current_page = 1
            while True:
                new_actions = await self._fetch_actions(diary_type, month, current_page)

                if not new_actions:
                    month_end = True
                    break

                actions += new_actions

                while stored and actions[-1].timestamp < stored[0].timestamp:  # overlap
                    # Get the whole span
                    i = 0
                    for stored_action in stored:
                        if stored_action.span_id == stored[0].span_id:
                            i += 1

                    # Split the span from all rows
                    action_span = stored[:i]
                    stored = stored[i:]

                    # Merge span with current fetch
                    try:
                        _, actions_c, _ = merge_time_series(actions, action_span)

                        actions_c = trim_right(actions_c)
                        logger.info(f"Loaded {len(actions_c)} cached entries")
                        actions += [copy_action(action) for action in actions_c]

                        if actions and actions[-1].timestamp <= start_time.timestamp():
                            # Since we're inside an overlapping span and this span covers our query
                            # we can safely break out
                            break

                        # Advance fetch
                        if actions_c:
                            advanced_pages = int(len(actions_c) / self.PAGE_LIMIT)
                            current_page += advanced_pages + 1
                            logger.info(
                                f"Caching saved fetching {advanced_pages} pages"
                            )
                            new_actions = await self._fetch_actions(
                                diary_type, month, current_page
                            )
                            actions += [
                                action
                                for action in new_actions
                                if action.time < actions_c[-1].time
                            ]
                    except ValueError:
                        pass
                    finally:
                        # Remove span from the database
                        for action in action_span:
                            session.delete(action)
                        if action_span:
                            session.delete(action_span[0].span)

                if actions and actions[-1].timestamp < start_time.timestamp():
                    if not stored or stored[0].timestamp < actions[-1].timestamp:
                        # Break if we have fetched beyond start time
                        # BUT only if there's no overlapping, if there is, we need to resolve it by fetch more
                        break

                current_page += 1

                if len(new_actions) < self.PAGE_LIMIT:
                    # Indicates that we've reached the beginning of the month
                    month_end = True
                    break

            if month_end and stored:
                logger.info(
                    "Renew all previous data as we've just fetched the whole month again"
                )
                # Remove all remaining stale data
                span = stored[0].span
                for action in stored:
                    session.delete(action)
                session.delete(span)

            if actions:
                # Create a span
                end = actions[0].time
                start = max(
                    datetime(year=end.year, month=end.month, day=1, tzinfo=end.tzinfo),
                    start_time,
                )
                span = DiaryActionSpan(
                    start_ts=int(start.timestamp()), end_ts=int(end.timestamp())
                )
                session.add(span)
                session.flush([span])

                # Attach span to actions
                for action in actions:
                    action.span_id = span.id

                session.bulk_save_objects(actions)
                session.commit()

                logger.info(f"Diary actions are cached successfully for month={month}")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=60)
    )
    async def _fetch_actions(
            self, diary_type: DiaryType, month: int, current_page: int
    ):
        match_time = datetime.now(self.server.tzoffset)
        while month != match_time.month:
            match_time -= relativedelta(months=1)
        year = match_time.year
        logger.info(f"Fetching month={month}, year={year}, current_page={current_page}")

        ledger = await self.client.request_ledger(
            detail=True,
            month=month,
            lang="en-us",
            params=dict(
                type=diary_type.value, current_page=current_page, limit=self.PAGE_LIMIT
            ),
        )

        return [
            DiaryAction(
                uid=self.uid,
                year=year,
                month=month,
                type=diary_type.value,
                action_id=a["action_id"],
                action=a["action"],
                timestamp=int(
                    dateutil.parser.parse(a["time"])
                        .replace(tzinfo=self.server.tzoffset)
                        .timestamp()
                ),
                amount=a["num"],
            )
            for a in ledger["list"]
        ]
