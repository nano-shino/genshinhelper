import unittest

from datamodels.diary_action import DiaryAction
from utils.ledger import merge_time_series


class LedgerTest(unittest.TestCase):
    def test_merge_time_series_empty(self):
        with self.assertRaises(Exception) as context:
            merge_time_series([], [])

        self.assertEqual(context.exception.args[0], 'Requires at least two overlapping timestamps')

    def test_merge_time_series_non_overlapping(self):
        with self.assertRaises(Exception) as context:
            merge_time_series([
                DiaryAction(timestamp=1),
                DiaryAction(timestamp=2),
            ], [
                DiaryAction(timestamp=3),
                DiaryAction(timestamp=4),
            ])

        self.assertEqual(context.exception.args[0], 'Requires at least two overlapping timestamps')

    def test_merge_time_series_all_overlapped(self):
        a = [
            DiaryAction(timestamp=1),
            DiaryAction(timestamp=2),
        ]
        b = [
            DiaryAction(timestamp=1),
            DiaryAction(timestamp=2),
        ]
        merged, a_complement, b_complement = merge_time_series(a, b)

        self.assertEqual(2, len(merged))
        self.assertListEqual(a_complement, [])
        self.assertListEqual(b_complement, [])

    def test_merge_time_series_slightly_overlapped(self):
        a = [
            DiaryAction(timestamp=1, amount=30),
            DiaryAction(timestamp=2, amount=40),
            DiaryAction(timestamp=2, amount=50),
        ]
        b = [
            DiaryAction(timestamp=1, amount=25),
            DiaryAction(timestamp=1, amount=30),
            DiaryAction(timestamp=2, amount=40),
        ]
        merged, a_complement, b_complement = merge_time_series(a, b)

        self.assertEqual(4, len(merged))
        self.assertListEqual(a_complement, [b[0]])
        self.assertListEqual(b_complement, [a[2]])

    def test_merge_time_series_medium_list(self):
        a = [
            DiaryAction(timestamp=1, amount=30),
            DiaryAction(timestamp=2, amount=30),
            DiaryAction(timestamp=2, amount=35),
            DiaryAction(timestamp=3, amount=33),
            DiaryAction(timestamp=4, amount=41),
            DiaryAction(timestamp=4, amount=42),
        ]
        b = [
            DiaryAction(timestamp=2, amount=30),
            DiaryAction(timestamp=3, amount=33),
            DiaryAction(timestamp=4, amount=42),
            DiaryAction(timestamp=4, amount=43),
            DiaryAction(timestamp=4, amount=41),
            DiaryAction(timestamp=4, amount=44),
            DiaryAction(timestamp=5, amount=50),
        ]
        merged, a_complement, b_complement = merge_time_series(a, b)

        self.assertEqual(9, len(merged))
        self.assertListEqual([x.timestamp for x in a_complement], [5, 4, 4])
        self.assertListEqual([x.timestamp for x in b_complement], [2, 1])

    def test_merge_time_series_inside(self):
        a = [
            DiaryAction(timestamp=4, amount=42),
            DiaryAction(timestamp=4, amount=41),
            DiaryAction(timestamp=3, amount=33),
        ]
        b = [
            DiaryAction(timestamp=5, amount=50),
            DiaryAction(timestamp=4, amount=44),
            DiaryAction(timestamp=4, amount=41),
            DiaryAction(timestamp=4, amount=43),
            DiaryAction(timestamp=4, amount=42),
            DiaryAction(timestamp=3, amount=33),
            DiaryAction(timestamp=3, amount=30),
            DiaryAction(timestamp=1, amount=30),
        ]
        merged, a_complement, b_complement = merge_time_series(a, b)

        self.assertEqual(8, len(merged))
        self.assertListEqual([x.timestamp for x in a_complement], [5, 4, 4, 3, 1])
        self.assertListEqual([x.timestamp for x in b_complement], [])
