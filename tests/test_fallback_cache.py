import tempfile
import unittest

import pandas as pd

from data.fallback_source import FallbackDataSource


def _build_frame(start: str, end: str) -> pd.DataFrame:
    idx = pd.date_range(start=start, end=end, freq='D')
    base = range(1, len(idx) + 1)
    return pd.DataFrame(
        {
            'open': base,
            'high': [x + 1 for x in base],
            'low': [x - 1 for x in base],
            'close': base,
            'volume': [100] * len(idx),
        },
        index=idx,
    )


class FakeFallbackDataSource(FallbackDataSource):
    def __init__(self, full_df: pd.DataFrame, cache_dir: str):
        super().__init__(priority=['fake'], cache_dir=cache_dir)
        self.full_df = full_df
        self.calls = []

    def _fetch_with_fallback(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        self.calls.append((start_date, end_date))
        start = f'{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}'
        end = f'{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}'
        return self.full_df.loc[start:end].copy()


class TestFallbackCache(unittest.TestCase):
    def test_should_backfill_front_when_requested_start_is_earlier_than_cache(self):
        full_df = _build_frame('2022-01-01', '2022-01-10')
        with tempfile.TemporaryDirectory() as tmpdir:
            source = FakeFallbackDataSource(full_df=full_df, cache_dir=tmpdir)

            first = source.get_data('000001', '20220103', '20220105', use_cache=True)
            second = source.get_data('000001', '20220101', '20220105', use_cache=True)

            self.assertEqual(len(first), 3)
            self.assertEqual(len(second), 5)
            self.assertEqual(second.index.min(), pd.Timestamp('2022-01-01'))
            self.assertIn(('20220101', '20220102'), source.calls)


if __name__ == '__main__':
    unittest.main()
