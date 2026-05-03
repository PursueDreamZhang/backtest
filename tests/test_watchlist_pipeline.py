import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from watchlist.pipeline import run_watchlist_strategy
from watchlist.reporting import write_overview_reports, write_reports
from watchlist.signals import SignalResult


class WatchlistReportingTests(unittest.TestCase):
    def test_should_write_json_csv_and_markdown(self):
        result = SignalResult(
            symbol="159770",
            name="机器人ETF",
            instrument_type="etf",
            mode="intraday",
            group="盘中触发",
            signal_timing="intraday",
            confidence="provisional",
            score=82,
            setup="MA40 弹簧盘中松开",
            latest_price=1.236,
            support=1.21,
            stop_loss=1.174,
            risk_to_stop_pct=5.02,
            signals=("实时价重新站上 MA5",),
            action="盘中优先盯",
            invalid_if="跌破止损",
            needs_close_confirmation=("收盘是否站上 MA5",),
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = write_reports(
                output_dir=tmp,
                direction="机器人",
                thesis="观察二次探底",
                mode="intraday",
                results=[result],
                run_date="2026-04-27",
            )

            payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "intraday")
            self.assertEqual(payload["summary"]["intraday_triggered"], 1)
            self.assertTrue(Path(paths["csv"]).exists())
            self.assertTrue(Path(paths["markdown"]).exists())

    def test_should_write_merged_overview_reports(self):
        triggered = SignalResult(
            symbol="002115",
            name="三维通信",
            instrument_type="stock",
            mode="close_confirmed",
            group="触发买点",
            signal_timing="close_confirmed",
            confidence="confirmed",
            score=80,
            setup="整理后第一根启动阳线",
            latest_price=14.0,
            support=13.2,
            stop_loss=12.4,
            risk_to_stop_pct=12.9,
            signals=("放量突破近20日高点",),
            action="轻仓试错，等待确认延续",
            invalid_if="跌回平台",
        )
        duplicated_lower_priority = SignalResult(
            symbol="002115",
            name="三维通信",
            instrument_type="stock",
            mode="close_confirmed",
            group="重点观察",
            signal_timing="close_confirmed",
            confidence="confirmed",
            score=72,
            setup="MA20 第一次回档",
            latest_price=14.0,
            support=13.2,
            stop_loss=12.4,
            risk_to_stop_pct=12.9,
            signals=("回踩 MA20",),
            action="等待右侧确认",
            invalid_if="跌破 MA20",
        )
        focus = SignalResult(
            symbol="600343",
            name="航天动力",
            instrument_type="stock",
            mode="close_confirmed",
            group="重点观察",
            signal_timing="close_confirmed",
            confidence="confirmed",
            score=74,
            setup="MA40 弹簧压紧",
            latest_price=32.84,
            support=33.1,
            stop_loss=31.1,
            risk_to_stop_pct=5.5,
            signals=("价格进入 MA40 附近",),
            action="等待重新站上 MA5 或放量转强",
            invalid_if="跌破 31.1",
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = write_overview_reports(
                output_dir=tmp,
                reports=[
                    {
                        "direction": "商业航天",
                        "summary": {"triggered": 1, "focus": 1, "wait": 0, "excluded": 0, "insufficient_data": 0},
                        "items": [triggered, focus],
                    },
                    {
                        "direction": "通信",
                        "summary": {"triggered": 0, "focus": 1, "wait": 0, "excluded": 0, "insufficient_data": 0},
                        "items": [duplicated_lower_priority],
                    },
                ],
                mode="close_confirmed",
                run_date="2026-04-28",
            )

            payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["triggered"], 1)
            self.assertEqual(payload["summary"]["focus"], 1)
            self.assertEqual(payload["items"][0]["symbol"], "002115")
            self.assertEqual(payload["items"][0]["directions"], ["商业航天", "通信"])
            self.assertEqual(payload["items"][0]["group"], "触发买点")
            self.assertEqual(payload["items"][1]["symbol"], "600343")
            self.assertIn("今日优先级清单", Path(paths["markdown"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(paths["csv"]).exists())
            html = Path(paths["html"]).read_text(encoding="utf-8")
            self.assertIn("观察标的总览", html)
            self.assertIn("今日优先级清单", html)
            self.assertIn("题材热度排行", html)


class WatchlistPipelineTests(unittest.TestCase):
    def test_should_run_pipeline_with_injected_data(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlist.json"
            config_path.write_text(
                '{"direction":"机器人","symbols":[{"symbol":"159770","type":"etf"}]}',
                encoding="utf-8",
            )

            result = run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date="20260427",
                mode="close_confirmed",
                frame_loader=lambda symbols, start_date, end_date: {"159770": frame},
                realtime_quote_loader=None,
            )

            self.assertTrue(Path(result["json"]).exists())
            self.assertTrue(Path(result["csv"]).exists())
            self.assertTrue(Path(result["markdown"]).exists())

    def test_should_pass_cache_only_to_frame_loader_when_supported(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )
        captured = {}

        def loader(symbols, start_date, end_date, **kwargs):
            captured["kwargs"] = kwargs
            return {"159770": frame}

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlist.json"
            config_path.write_text(
                '{"direction":"机器人","symbols":[{"symbol":"159770","type":"etf"}]}',
                encoding="utf-8",
            )

            run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date="20260427",
                mode="close_confirmed",
                frame_loader=loader,
                realtime_quote_loader=None,
                cache_only=True,
            )

            self.assertEqual(captured["kwargs"], {"cache_only": True})

    def test_should_prefer_cache_for_current_close_confirmed_day_when_supported(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )
        captured = {}

        def loader(symbols, start_date, end_date, **kwargs):
            captured["kwargs"] = kwargs
            return {"159770": frame}

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlist.json"
            config_path.write_text(
                '{"direction":"机器人","symbols":[{"symbol":"159770","type":"etf"}]}',
                encoding="utf-8",
            )
            today = datetime.now().strftime("%Y%m%d")

            run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date=today,
                mode="close_confirmed",
                frame_loader=loader,
                realtime_quote_loader=None,
            )

            self.assertEqual(captured["kwargs"], {"cache_only": False, "prefer_cache_for_current_day": True})

    def test_should_load_intraday_history_only_through_previous_trading_day(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )
        captured = {}

        def loader(symbols, start_date, end_date, **kwargs):
            captured["start_date"] = start_date
            captured["end_date"] = end_date
            captured["kwargs"] = kwargs
            return {"159770": frame}

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlist.json"
            config_path.write_text(
                '{"direction":"机器人","symbols":[{"symbol":"159770","type":"etf"}]}',
                encoding="utf-8",
            )
            today = datetime.now().strftime("%Y%m%d")
            previous_day = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

            run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date=today,
                mode="intraday",
                frame_loader=loader,
                realtime_quote_loader=lambda symbols: [
                    {
                        "symbol": "159770",
                        "price": 10.0,
                        "open": 10.0,
                        "high": 10.1,
                        "low": 9.9,
                        "previous_close": 10.0,
                        "volume": 1000,
                    }
                ],
            )

            self.assertEqual(captured["start_date"], "20260101")
            self.assertEqual(captured["end_date"], previous_day)
            self.assertEqual(captured["kwargs"], {"cache_only": False})

    def test_should_skip_close_confirmed_symbol_when_current_day_data_is_missing(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlist.json"
            config_path.write_text(
                '{"direction":"机器人","symbols":[{"symbol":"159770","type":"etf"}]}',
                encoding="utf-8",
            )

            result = run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date="20260430",
                mode="close_confirmed",
                frame_loader=lambda symbols, start_date, end_date: {"159770": frame},
                realtime_quote_loader=None,
            )

            payload = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["items"][0]["group"], "数据不足")
            self.assertEqual(payload["items"][0]["setup"], "缺少当日收盘数据")

    def test_should_run_multiple_watchlists_into_direction_subdirectories(self):
        closes = [10.0] * 80
        frame = pd.DataFrame(
            {
                "open": closes,
                "high": [10.2] * 80,
                "low": [9.8] * 80,
                "close": closes,
                "volume": [1000] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80),
        )

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "watchlists.json"
            config_path.write_text(
                """
                {
                  "watchlists": [
                    {"direction":"半导体","symbols":[{"symbol":"688012","type":"stock"}]},
                    {"direction":"商业航天","symbols":[{"symbol":"001270","type":"stock"}]}
                  ]
                }
                """,
                encoding="utf-8",
            )

            result = run_watchlist_strategy(
                config_path=str(config_path),
                output_dir=tmp,
                start_date="20260101",
                end_date="20260427",
                mode="close_confirmed",
                frame_loader=lambda symbols, start_date, end_date: {
                    "688012": frame,
                    "001270": frame,
                },
                realtime_quote_loader=None,
            )

            self.assertTrue(Path(result["半导体"]["json"]).exists())
            self.assertTrue(Path(result["商业航天"]["json"]).exists())
            self.assertTrue(Path(result["overview"]["json"]).exists())
            self.assertTrue(Path(result["overview"]["csv"]).exists())
            self.assertTrue(Path(result["overview"]["markdown"]).exists())
            self.assertTrue(Path(result["overview"]["html"]).exists())


if __name__ == "__main__":
    unittest.main()
