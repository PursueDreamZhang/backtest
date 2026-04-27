import unittest

import pandas as pd

from research.etf_universe import EtfUniverseEntry
from research.reporting import summarize_latest_state


class MarketRegimeReportingTests(unittest.TestCase):
    def test_should_build_latest_summary_with_top_five_and_direction_labels(self):
        daily_state = pd.DataFrame(
            {
                "date": ["2024-02-19", "2024-02-20"],
                "market_stage": ["混沌", "主升"],
                "market_stage_score": [0.50, 0.75],
                "leader_etf_top1": ["X", "A"],
                "leader_etf_top2": ["Y", "B"],
                "leader_etf_top3": ["Z", "C"],
                "leader_etf_top4": ["M", "D"],
                "leader_etf_top5": ["N", "E"],
                "leader_direction_top1": ["旧方向", "TMT"],
                "leader_direction_top2": ["旧方向2", "成长"],
                "leader_direction_summary": ["旧摘要", "TMT / 成长 / 创业板"],
                "can_open_new_position": [False, True],
                "open_position_reason": ["stage_or_leader_gap_not_enough", "stage_ok_and_leader_gap_positive"],
            }
        )
        leaderboard = pd.DataFrame(
            {
                "date": ["2024-02-20"] * 5,
                "symbol": ["A", "B", "C", "D", "E"],
                "rank": [1.0, 2.0, 3.0, 4.0, 5.0],
                "composite_score": [0.91, 0.83, 0.75, 0.66, 0.58],
                "daily_return": [0.02, 0.01, -0.03, 0.04, 0.00],
                "daily_return_pct": [2.0, 1.0, -3.0, 4.0, 0.0],
                "open_to_close_return": [0.01, 0.02, -0.01, 0.03, 0.00],
                "high_to_close_gap": [0.03, 0.01, 0.04, 0.02, 0.00],
            }
        )
        universe = [
            EtfUniverseEntry("A", "A基金", ("成长",), True, False),
            EtfUniverseEntry("B", "B基金", ("TMT",), False, True),
            EtfUniverseEntry("C", "C基金", ("通信",), False, True),
            EtfUniverseEntry("D", "D基金", ("消费",), False, True),
            EtfUniverseEntry("E", "E基金", ("电池",), False, True),
        ]

        summary = summarize_latest_state(daily_state, leaderboard, universe)

        self.assertEqual(summary["date"], "2024-02-20")
        self.assertEqual(summary["market_stage"], "主升")
        self.assertEqual(summary["leader_direction_summary"], "TMT / 成长 / 创业板")
        self.assertEqual(len(summary["top5"]), 5)
        self.assertEqual(summary["top5"][0]["symbol"], "A")
        self.assertEqual(summary["top5"][0]["name"], "A基金")
        self.assertEqual(summary["top5"][0]["daily_return_pct"], 2.0)
        self.assertEqual(summary["top5"][0]["open_to_close_return"], 0.01)
        self.assertEqual(summary["top5"][0]["high_to_close_gap"], 0.03)
        self.assertEqual(summary["top5"][4]["symbol"], "E")


if __name__ == "__main__":
    unittest.main()
