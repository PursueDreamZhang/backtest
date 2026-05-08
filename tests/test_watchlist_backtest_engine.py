import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from watchlist_backtest.engine import run_watchlist_backtest


class WatchlistBacktestEngineTests(unittest.TestCase):
    def test_should_generate_backtest_outputs_and_execute_trade_flow(self):
        diary = pd.DataFrame(
            [
                {
                    "trade_date": "20260401",
                    "symbol": "000001",
                    "name": "测试标的",
                    "direction": "测试方向",
                    "thesis": "测试逻辑",
                    "group": "触发买点",
                    "setup": "双底或二次压紧",
                    "score": 80,
                    "latest_price": 10.0,
                    "support": 9.6,
                    "stop_loss": 9.5,
                    "risk_to_stop_pct": 5.26,
                    "action": "次日开盘试仓",
                },
                {
                    "trade_date": "20260402",
                    "symbol": "000001",
                    "name": "测试标的",
                    "direction": "测试方向",
                    "thesis": "测试逻辑",
                    "group": "重点观察",
                    "setup": "双底或二次压紧",
                    "score": 68,
                    "latest_price": 9.6,
                    "support": 9.5,
                    "stop_loss": 9.5,
                    "risk_to_stop_pct": 1.05,
                    "action": "观察右侧确认",
                },
                {
                    "trade_date": "20260403",
                    "symbol": "000001",
                    "name": "测试标的",
                    "direction": "测试方向",
                    "thesis": "测试逻辑",
                    "group": "排除观察",
                    "setup": "双底或二次压紧",
                    "score": 40,
                    "latest_price": 9.2,
                    "support": 9.3,
                    "stop_loss": 9.5,
                    "risk_to_stop_pct": -3.16,
                    "action": "跌破结构支撑",
                },
            ]
        )
        frames = {
            "000001": pd.DataFrame(
                [
                    {"open": 10.0, "high": 10.2, "low": 9.8, "close": 10.0},
                    {"open": 10.0, "high": 10.1, "low": 9.4, "close": 9.6},
                    {"open": 9.5, "high": 9.6, "low": 9.3, "close": 9.4},
                ],
                index=pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"]),
            )
        }

        with tempfile.TemporaryDirectory() as tmp:
            with patch("watchlist_backtest.engine.build_signal_diary", return_value=(diary, frames)):
                result = run_watchlist_backtest(
                    config_path="/tmp/ignored.json",
                    start_date="20260401",
                    end_date="20260403",
                    output_dir=tmp,
                    initial_cash=100000,
                    max_positions=2,
                    position_size_pct=0.5,
                    max_hold_days=5,
                )

            self.assertTrue(Path(result["summary"]).exists())
            self.assertTrue(Path(result["trades"]).exists())
            self.assertTrue(Path(result["equity_curve"]).exists())
            self.assertTrue(Path(result["signal_diary"]).exists())
            self.assertTrue(Path(result["html"]).exists())

            summary = json.loads(Path(result["summary"]).read_text(encoding="utf-8"))
            self.assertIn("总收益率(%)", summary)
            self.assertEqual(summary["交易笔数"], 1)

            trades = pd.read_csv(result["trades"])
            self.assertEqual(len(trades), 1)
            self.assertEqual(str(trades.iloc[0]["代码"]).zfill(6), "000001")
            self.assertEqual(int(trades.iloc[0]["买入日"]), 20260402)
            self.assertEqual(trades.iloc[0]["卖出原因"], "触发止损")
            self.assertEqual(list(trades.columns[:5]), ["代码", "名称", "方向", "模型", "信号日"])

    def test_should_rank_higher_score_signal_first_when_slots_are_limited(self):
        diary = pd.DataFrame(
            [
                {
                    "trade_date": "20260401",
                    "symbol": "000001",
                    "name": "高分标的",
                    "direction": "方向A",
                    "thesis": "测试逻辑",
                    "group": "触发买点",
                    "setup": "MA20 第一次回档",
                    "score": 90,
                    "latest_price": 10.0,
                    "support": 9.6,
                    "stop_loss": 9.5,
                    "risk_to_stop_pct": 5.0,
                    "action": "次日开盘试仓",
                },
                {
                    "trade_date": "20260401",
                    "symbol": "000002",
                    "name": "低分标的",
                    "direction": "方向B",
                    "thesis": "测试逻辑",
                    "group": "触发买点",
                    "setup": "MA20 第一次回档",
                    "score": 70,
                    "latest_price": 10.0,
                    "support": 9.6,
                    "stop_loss": 9.5,
                    "risk_to_stop_pct": 5.0,
                    "action": "次日开盘试仓",
                },
                {
                    "trade_date": "20260402",
                    "symbol": "000001",
                    "name": "高分标的",
                    "direction": "方向A",
                    "thesis": "测试逻辑",
                    "group": "重点观察",
                    "setup": "MA20 第一次回档",
                    "score": 80,
                    "latest_price": 10.4,
                    "support": 9.7,
                    "stop_loss": 9.5,
                    "risk_to_stop_pct": 9.47,
                    "action": "持有观察",
                },
                {
                    "trade_date": "20260402",
                    "symbol": "000002",
                    "name": "低分标的",
                    "direction": "方向B",
                    "thesis": "测试逻辑",
                    "group": "重点观察",
                    "setup": "MA20 第一次回档",
                    "score": 65,
                    "latest_price": 10.1,
                    "support": 9.7,
                    "stop_loss": 9.5,
                    "risk_to_stop_pct": 6.32,
                    "action": "持有观察",
                },
            ]
        )
        frames = {
            "000001": pd.DataFrame(
                [
                    {"open": 10.0, "high": 10.2, "low": 9.8, "close": 10.0},
                    {"open": 10.1, "high": 10.5, "low": 9.9, "close": 10.4},
                ],
                index=pd.to_datetime(["2026-04-01", "2026-04-02"]),
            ),
            "000002": pd.DataFrame(
                [
                    {"open": 10.0, "high": 10.2, "low": 9.8, "close": 10.0},
                    {"open": 10.0, "high": 10.2, "low": 9.9, "close": 10.1},
                ],
                index=pd.to_datetime(["2026-04-01", "2026-04-02"]),
            ),
        }

        with tempfile.TemporaryDirectory() as tmp:
            with patch("watchlist_backtest.engine.build_signal_diary", return_value=(diary, frames)):
                result = run_watchlist_backtest(
                    config_path="/tmp/ignored.json",
                    start_date="20260401",
                    end_date="20260402",
                    output_dir=tmp,
                    initial_cash=100000,
                    max_positions=1,
                    position_size_pct=0.5,
                    max_hold_days=10,
                )

            trades = pd.read_csv(result["trades"])
            self.assertEqual(len(trades), 0)

            equity = pd.read_csv(result["equity_curve"])
            self.assertEqual(int(equity.iloc[-1]["持仓数量"]), 1)
            self.assertEqual(list(equity.columns), ["交易日", "现金", "持仓市值", "总权益", "持仓数量"])

            summary = json.loads(Path(result["summary"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["交易笔数"], 0)
