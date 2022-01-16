from typing import List, Tuple

from datamodels.diary_action import DiaryAction


def merge_time_series(
    series_a: List[DiaryAction], series_b: List[DiaryAction]
) -> Tuple[List[DiaryAction], List[DiaryAction], List[DiaryAction]]:
    """
    Merge two time series and dedup the overlapping parts.

    :param series_a: The first series.
    :param series_b: The second series.
    :return: A tuple of:
                merged_series: the combination of series a and b
                a_complement: what elements series a is missing from merged
                b_complement: what elements series b is missing from merged
    """
    a = sorted(series_a, key=lambda x: x.timestamp)
    b = sorted(series_b, key=lambda x: x.timestamp)

    # Ensure that we have sufficient overlapping
    overlaps = {x.timestamp for x in a} & {x.timestamp for x in b}
    if len(overlaps) < 2:
        raise ValueError("Requires at least two overlapping timestamps")

    merged = []
    a_complement = []
    b_complement = []
    while a and b:
        if a[-1].timestamp > b[-1].timestamp:
            merged.append(a.pop())
            b_complement.append(merged[-1])
        elif a[-1].timestamp < b[-1].timestamp:
            merged.append(b.pop())
            a_complement.append(merged[-1])
        else:
            a_bucket = [a.pop()]
            b_bucket = [b.pop()]
            while a and a[-1].timestamp == a_bucket[0].timestamp:
                a_bucket.append(a.pop())
            while b and b[-1].timestamp == b_bucket[0].timestamp:
                b_bucket.append(b.pop())
            if len(a_bucket) < len(b_bucket):
                merged.extend(b_bucket)
                a_complement.extend(diary_action_subtract(b_bucket, a_bucket))
            else:
                merged.extend(a_bucket)
                b_complement.extend(diary_action_subtract(a_bucket, b_bucket))

    while a:
        merged.append(a.pop())
        b_complement.append(merged[-1])
    while b:
        merged.append(b.pop())
        a_complement.append(merged[-1])

    return merged, a_complement, b_complement


def diary_action_subtract(
    series_a: List[DiaryAction], series_b: List[DiaryAction]
) -> List[DiaryAction]:
    """Subtracts b from a"""
    return [
        x
        for x in series_a
        if all(
            x.timestamp != y.timestamp
            or x.action != y.action
            or x.action_id != y.action_id
            or x.type != y.type
            or x.amount != y.amount
            or x.uid != y.uid
            or x.month != y.month
            or x.year != y.year
            for y in series_b
        )
    ]


def trim_right(series: List[DiaryAction]) -> List[DiaryAction]:
    """
    Trim the last timestamp.

    :param series: The original series.
    :return: The trimmed series.
    """
    j = len(series) - 2
    while j >= 0:
        if series[j].timestamp != series[-1].timestamp:
            break
        j -= 1

    return series[: j + 1]


def copy_action(action: DiaryAction):
    """
    Copy DiaryAction to a new object.

    :param action: The original object.
    :return: The new object.
    """
    return DiaryAction(
        uid=action.uid,
        year=action.year,
        month=action.month,
        type=action.type,
        action_id=action.action_id,
        action=action.action,
        timestamp=action.timestamp,
        amount=action.amount,
    )
