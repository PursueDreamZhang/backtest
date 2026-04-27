import unittest

import pandas as pd

from research.etf_universe import EtfUniverseEntry
from research.visualization import (
    build_dashboard_payload,
    build_stage_bands,
)


class MarketRegimeVisualizationTests(unittest.TestCase):
    def test_should_merge_contiguous_stage_ranges_into_bands(self):
        daily_state = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
                ),
                "market_stage": ["启动", "启动", "混沌", "混沌", "主升"],
            }
        )

        bands = build_stage_bands(daily_state)

        self.assertEqual(len(bands), 3)
        self.assertEqual(bands[0]["stage"], "启动")
        self.assertEqual(bands[0]["start_idx"], 0)
        self.assertEqual(bands[0]["end_idx"], 1)
        self.assertEqual(bands[1]["stage"], "混沌")
        self.assertEqual(bands[1]["start_idx"], 2)
        self.assertEqual(bands[1]["end_idx"], 3)
        self.assertEqual(bands[2]["stage"], "主升")
        self.assertEqual(bands[2]["start_idx"], 4)
        self.assertEqual(bands[2]["end_idx"], 4)

    def test_should_default_to_showing_top_five_and_mark_legend_labels(self):
        index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
        universe = [
            EtfUniverseEntry(
                symbol="510050",
                name="上证50ETF华夏",
                tags=("市场代理", "宽基"),
                is_market_proxy=True,
                is_theme_proxy=False,
            ),
            EtfUniverseEntry(
                symbol="512010",
                name="医药ETF易方达",
                tags=("医药",),
                is_market_proxy=False,
                is_theme_proxy=True,
            ),
            EtfUniverseEntry(
                symbol="510300",
                name="沪深300ETF",
                tags=("市场代理", "宽基"),
                is_market_proxy=True,
                is_theme_proxy=False,
            ),
            EtfUniverseEntry(
                symbol="159915",
                name="创业板ETF",
                tags=("成长",),
                is_market_proxy=True,
                is_theme_proxy=False,
            ),
            EtfUniverseEntry(
                symbol="588060",
                name="科创50ETF",
                tags=("TMT",),
                is_market_proxy=True,
                is_theme_proxy=False,
            ),
        ]
        frames = {
            "510050": pd.DataFrame(
                {
                    "close": [10.0, 11.0, 12.0],
                },
                index=index,
            ),
            "512010": pd.DataFrame(
                {
                    "close": [20.0, 19.0, 21.0],
                },
                index=index,
            ),
            "510300": pd.DataFrame(
                {
                    "close": [30.0, 31.0, 32.0],
                },
                index=index,
            ),
            "159915": pd.DataFrame(
                {
                    "close": [40.0, 42.0, 43.0],
                },
                index=index,
            ),
            "588060": pd.DataFrame(
                {
                    "close": [50.0, 49.0, 51.0],
                },
                index=index,
            ),
        }
        daily_state = pd.DataFrame(
            {
                "date": index,
                "market_stage": ["启动", "混沌", "主升"],
                "leader_direction_summary": ["消费", "TMT", "成长 / TMT"],
                "leader_etf_top1": ["510050", "512010", "512010"],
                "leader_etf_top2": ["512010", "510050", "510050"],
                "leader_etf_top3": ["", "", "510300"],
                "leader_etf_top4": ["", "", "159915"],
                "leader_etf_top5": ["", "", "588060"],
            }
        )
        leaderboard = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03", "2024-01-04"] * 5,
                "symbol": ["510050"] * 3 + ["512010"] * 3 + ["510300"] * 3 + ["159915"] * 3 + ["588060"] * 3,
                "daily_return_pct": [0.0, 10.0, 9.0909, 0.0, -5.0, 10.5263, 0.0, 3.0, 3.2258, 0.0, 5.0, 2.3810, 0.0, -2.0, 4.0816],
                "open_to_close_return": [0.01, 0.02, 0.03, -0.01, -0.02, 0.04, 0.0, 0.01, 0.02, 0.0, 0.03, 0.01, 0.0, -0.01, 0.03],
                "high_to_close_gap": [0.02, 0.01, 0.03, 0.05, 0.02, 0.01, 0.01, 0.01, 0.02, 0.03, 0.01, 0.01, 0.04, 0.02, 0.02],
            }
        )

        payload = build_dashboard_payload(
            universe=universe,
            frames=frames,
            daily_state=daily_state,
            leaderboard=leaderboard,
            title="测试面板",
        )

        self.assertEqual(payload["title"], "测试面板")
        self.assertEqual(payload["latest_snapshot"]["market_stage"], "主升")
        self.assertEqual(payload["latest_snapshot"]["leader_direction_summary"], "成长 / TMT")
        self.assertEqual(payload["latest_snapshot"]["top5_symbols"], ["512010", "510050", "510300", "159915", "588060"])
        self.assertEqual(len(payload["latest_snapshot"]["top5_details"]), 5)
        self.assertEqual(payload["latest_snapshot"]["top5_details"][0]["rank"], 1)
        self.assertEqual(payload["latest_snapshot"]["top5_details"][0]["symbol"], "512010")
        self.assertEqual(payload["latest_snapshot"]["top5_details"][0]["daily_return_pct"], 10.5263)
        self.assertEqual(len(payload["bands"]), 3)
        self.assertEqual(len(payload["traces"]), 5)
        self.assertEqual(payload["x_labels"], ["2024-01-02", "2024-01-03", "2024-01-04"])
        market_trace = payload["traces"][0]
        theme_trace = payload["traces"][1]
        self.assertEqual(market_trace["symbol"], "510050")
        self.assertEqual(market_trace["display_name"], "[2] 510050 上证50ETF华夏")
        self.assertTrue(market_trace["visible"])
        self.assertEqual(market_trace["x"], [0, 1, 2])
        self.assertEqual(market_trace["dates"], ["2024-01-02", "2024-01-03", "2024-01-04"])
        self.assertEqual(market_trace["stages"], ["启动", "混沌", "主升"])
        self.assertEqual(market_trace["y"], [1.0, 1.1, 1.2])
        self.assertEqual(market_trace["daily_return_pct"], [0.0, 10.0, 9.0909])
        self.assertEqual(market_trace["open_to_close_return"], [0.01, 0.02, 0.03])
        self.assertEqual(market_trace["high_to_close_gap"], [0.02, 0.01, 0.03])
        self.assertEqual(market_trace["category"], "market")
        self.assertNotIn("legendgroup", market_trace)
        self.assertEqual(theme_trace["symbol"], "512010")
        self.assertEqual(theme_trace["display_name"], "[1] 512010 医药ETF易方达")
        self.assertTrue(theme_trace["visible"])
        self.assertEqual(theme_trace["x"], [0, 1, 2])
        self.assertEqual(theme_trace["stages"], ["启动", "混沌", "主升"])
        self.assertEqual(theme_trace["y"], [1.0, 0.95, 1.05])
        self.assertEqual(theme_trace["category"], "theme")
        self.assertNotIn("legendgroup", theme_trace)


if __name__ == "__main__":
    unittest.main()
