# Watchlist Execution Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable watchlist strategy that reads user-provided directions and symbols, loads recent market data plus optional realtime quotes, evaluates the spring/trend rules, and outputs prioritized JSON/CSV/Markdown reports.

**Architecture:** Add a focused `watchlist` research package next to the existing `research` package. Reuse `research.data_loader.load_symbol_frames()` for historical daily bars and `data.realtime_quote_source.RealtimeQuoteSource` for intraday quotes, keeping signal computation pure and testable.

**Tech Stack:** Python stdlib, pandas, existing data sources, unittest.

---

## File Structure

- Create: `watchlist/__init__.py`
  - Package marker and public exports.
- Create: `watchlist/config.py`
  - Dataclasses and JSON loader for direction/watchlist config.
- Create: `watchlist/indicators.py`
  - Pure indicator helpers for moving averages, drawdown, support distance, trend state, and volume progress.
- Create: `watchlist/signals.py`
  - Pure rule engine for MA40 spring, MA20 first pullback, double-bottom, launch candle, exclusion, scoring, and grouping.
- Create: `watchlist/reporting.py`
  - JSON/CSV/Markdown output helpers.
- Create: `watchlist/pipeline.py`
  - Orchestrates config loading, historical data, realtime quotes, signal evaluation, and report writing.
- Create: `scripts/run_watchlist_strategy.py`
  - CLI entrypoint.
- Create: `config/watchlist.example.json`
  - Example user input.
- Create: `tests/test_watchlist_config.py`
  - Config parsing tests.
- Create: `tests/test_watchlist_signals.py`
  - Rule-engine tests.
- Create: `tests/test_watchlist_pipeline.py`
  - Pipeline orchestration tests with injected loaders.
- Modify: `README.md`
  - Add watchlist usage.

## Task 1: Config Loader

**Files:**
- Create: `watchlist/__init__.py`
- Create: `watchlist/config.py`
- Create: `config/watchlist.example.json`
- Test: `tests/test_watchlist_config.py`

- [ ] **Step 1: Write failing config loader test**

```python
import tempfile
import unittest
from pathlib import Path

from watchlist.config import load_watchlist_config


class WatchlistConfigTests(unittest.TestCase):
    def test_should_load_watchlist_config_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlist.json"
            path.write_text(
                """
                {
                  "direction": "机器人",
                  "thesis": "观察二次探底",
                  "symbols": [
                    {"symbol": "159770", "name": "机器人ETF", "type": "etf"},
                    {"symbol": "300124"}
                  ]
                }
                """,
                encoding="utf-8",
            )

            config = load_watchlist_config(path)

            self.assertEqual(config.direction, "机器人")
            self.assertEqual(config.thesis, "观察二次探底")
            self.assertEqual([item.symbol for item in config.symbols], ["159770", "300124"])
            self.assertEqual(config.symbols[1].name, "")
            self.assertEqual(config.symbols[1].instrument_type, "stock")
            self.assertEqual(config.symbols[1].role, "")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_config -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'watchlist'`.

- [ ] **Step 3: Implement minimal config loader**

```python
# watchlist/config.py
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from data.realtime_quote_source import normalize_cn_symbol


@dataclass(frozen=True)
class WatchSymbol:
    symbol: str
    name: str = ""
    instrument_type: str = "stock"
    role: str = ""


@dataclass(frozen=True)
class WatchlistConfig:
    direction: str
    thesis: str
    symbols: tuple[WatchSymbol, ...]


def load_watchlist_config(path: str | Path) -> WatchlistConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    symbols = []
    for item in payload.get("symbols", []):
        symbols.append(
            WatchSymbol(
                symbol=normalize_cn_symbol(item["symbol"]),
                name=str(item.get("name", "")),
                instrument_type=str(item.get("type", "stock")),
                role=str(item.get("role", "")),
            )
        )
    if not symbols:
        raise ValueError("watchlist config 至少需要一个 symbols 条目")
    return WatchlistConfig(
        direction=str(payload.get("direction", "")),
        thesis=str(payload.get("thesis", "")),
        symbols=tuple(symbols),
    )
```

```python
# watchlist/__init__.py
"""Watchlist execution strategy package."""
```

```json
{
  "direction": "机器人",
  "thesis": "板块可能完成二次探底，观察是否重新转强",
  "symbols": [
    {
      "symbol": "159770",
      "name": "机器人ETF",
      "type": "etf",
      "role": "板块代理"
    },
    {
      "symbol": "300124",
      "name": "汇川技术",
      "type": "stock",
      "role": "中军"
    }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_config -v
```

Expected: PASS.

## Task 2: Indicator Helpers

**Files:**
- Create: `watchlist/indicators.py`
- Test: `tests/test_watchlist_signals.py`

- [ ] **Step 1: Write failing indicator tests**

```python
import unittest

import pandas as pd

from watchlist.indicators import enrich_daily_indicators, support_distance_pct, volume_progress


class WatchlistIndicatorTests(unittest.TestCase):
    def test_should_compute_ma_and_support_distance(self):
        frame = pd.DataFrame(
            {
                "open": [10.0] * 45,
                "high": [10.5] * 45,
                "low": [9.5] * 45,
                "close": [10.0] * 44 + [10.2],
                "volume": [1000] * 45,
            },
            index=pd.date_range("2026-01-01", periods=45),
        )

        enriched = enrich_daily_indicators(frame)

        self.assertAlmostEqual(enriched.iloc[-1]["ma40"], 10.005, places=3)
        self.assertAlmostEqual(support_distance_pct(10.2, 10.0), 2.0)

    def test_should_compute_volume_progress(self):
        self.assertAlmostEqual(volume_progress(current_volume=500, avg_volume=1000), 0.5)
        self.assertIsNone(volume_progress(current_volume=500, avg_volume=0))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_signals.WatchlistIndicatorTests -v
```

Expected: FAIL with missing `watchlist.indicators`.

- [ ] **Step 3: Implement indicator helpers**

```python
from __future__ import annotations

import pandas as pd


def enrich_daily_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy().sort_index()
    work["ma5"] = work["close"].rolling(5).mean()
    work["ma20"] = work["close"].rolling(20).mean()
    work["ma40"] = work["close"].rolling(40).mean()
    work["ma120"] = work["close"].rolling(120).mean()
    work["vol5"] = work["volume"].rolling(5).mean()
    work["vol20"] = work["volume"].rolling(20).mean()
    work["ret20"] = work["close"] / work["close"].shift(20) - 1.0
    work["ret40"] = work["close"] / work["close"].shift(40) - 1.0
    work["high20"] = work["high"].rolling(20).max()
    work["low20"] = work["low"].rolling(20).min()
    work["low60"] = work["low"].rolling(60).min()
    work["drawdown20"] = work["close"] / work["high"].rolling(20).max() - 1.0
    return work


def support_distance_pct(price: float, support: float | None) -> float | None:
    if support is None or support == 0:
        return None
    return (price / support - 1.0) * 100


def volume_progress(current_volume: float | None, avg_volume: float | None) -> float | None:
    if current_volume is None or avg_volume in (None, 0):
        return None
    return current_volume / avg_volume
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_signals.WatchlistIndicatorTests -v
```

Expected: PASS.

## Task 3: Signal Rule Engine

**Files:**
- Create: `watchlist/signals.py`
- Modify: `tests/test_watchlist_signals.py`

- [ ] **Step 1: Write failing tests for MA40 spring and exclusion**

```python
from watchlist.signals import evaluate_symbol


class WatchlistSignalTests(unittest.TestCase):
    def _frame(self, closes, volumes=None):
        volumes = volumes or [1000] * len(closes)
        return pd.DataFrame(
            {
                "open": closes,
                "high": [price * 1.01 for price in closes],
                "low": [price * 0.99 for price in closes],
                "close": closes,
                "volume": volumes,
            },
            index=pd.date_range("2026-01-01", periods=len(closes)),
        )

    def test_should_trigger_close_confirmed_ma40_spring(self):
        closes = [10.0] * 45 + [11.0] * 15 + [10.2, 10.1, 10.05, 10.15, 10.35]
        volumes = [1000] * 60 + [700, 700, 700, 700, 700]

        result = evaluate_symbol(
            symbol="159770",
            name="机器人ETF",
            instrument_type="etf",
            frame=self._frame(closes, volumes),
            mode="close_confirmed",
        )

        self.assertEqual(result.group, "触发买点")
        self.assertEqual(result.confidence, "confirmed")
        self.assertIn("MA40", result.setup)

    def test_should_mark_intraday_invalid_when_price_breaks_stop(self):
        closes = [10.0] * 80
        quote = {
            "price": 9.4,
            "open": 10.0,
            "previous_close": 10.0,
            "high": 10.1,
            "low": 9.4,
            "volume": 500,
            "fetched_at": "2026-04-27T10:30:00",
        }

        result = evaluate_symbol(
            symbol="159770",
            name="机器人ETF",
            instrument_type="etf",
            frame=self._frame(closes),
            mode="intraday",
            realtime_quote=quote,
        )

        self.assertEqual(result.group, "盘中失效")
        self.assertEqual(result.confidence, "provisional")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_signals -v
```

Expected: FAIL with missing `watchlist.signals`.

- [ ] **Step 3: Implement minimal rule engine**

Implement these dataclasses and functions:

```python
@dataclass(frozen=True)
class SignalResult:
    symbol: str
    name: str
    instrument_type: str
    mode: str
    group: str
    signal_timing: str
    confidence: str
    score: int
    setup: str
    latest_price: float
    support: float | None
    stop_loss: float | None
    risk_to_stop_pct: float | None
    signals: tuple[str, ...]
    action: str
    invalid_if: str
    needs_close_confirmation: tuple[str, ...] = ()
```

`evaluate_symbol()` should:

- Enrich historical frame with `enrich_daily_indicators()`.
- Use realtime quote for `intraday`, latest daily row for `close_confirmed`.
- Evaluate exclusion first.
- Evaluate MA40 spring, MA20 pullback, double-bottom, launch candle.
- Pick highest priority group in this order:
  - `盘中失效` / `排除观察`
  - `盘中触发` / `触发买点`
  - `盘中预警` / `重点观察`
  - `盘中等待` / `等待回调`
  - `数据不足`
- Compute score from the 100-point table in `docs/观察标的执行策略规则.md`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_signals -v
```

Expected: PASS.

## Task 4: Reporting Outputs

**Files:**
- Create: `watchlist/reporting.py`
- Test: `tests/test_watchlist_pipeline.py`

- [ ] **Step 1: Write failing report test**

```python
import json
import tempfile
import unittest
from pathlib import Path

from watchlist.reporting import write_reports
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_pipeline.WatchlistReportingTests -v
```

Expected: FAIL with missing `watchlist.reporting`.

- [ ] **Step 3: Implement reporting**

`write_reports()` should create:

- `watchlist_report.json`
- `watchlist_report.csv`
- `watchlist_report.md`

The JSON must include:

```python
{
    "run_date": run_date,
    "mode": mode,
    "direction": direction,
    "thesis": thesis,
    "summary": summary,
    "items": [asdict(result) for result in sorted_results],
}
```

Sort results by group priority then score descending.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_pipeline.WatchlistReportingTests -v
```

Expected: PASS.

## Task 5: Pipeline and CLI

**Files:**
- Create: `watchlist/pipeline.py`
- Create: `scripts/run_watchlist_strategy.py`
- Modify: `tests/test_watchlist_pipeline.py`

- [ ] **Step 1: Write failing pipeline test**

```python
from watchlist.pipeline import run_watchlist_strategy


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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_pipeline.WatchlistPipelineTests -v
```

Expected: FAIL with missing `watchlist.pipeline`.

- [ ] **Step 3: Implement pipeline and CLI**

`run_watchlist_strategy()` signature:

```python
def run_watchlist_strategy(
    config_path: str,
    output_dir: str,
    start_date: str,
    end_date: str,
    *,
    mode: str = "close_confirmed",
    frame_loader=None,
    realtime_quote_loader=None,
) -> dict[str, str]:
```

Default loaders:

- `frame_loader = research.data_loader.load_symbol_frames`
- `realtime_quote_loader = data.realtime_quote_source.RealtimeQuoteSource().get_quotes`

CLI arguments:

```text
--config
--output-dir
--start-date
--end-date
--mode intraday|close_confirmed
--cache-only
```

For `intraday`, call `RealtimeQuoteSource().get_quotes(symbols)` and pass each quote into `evaluate_symbol()`.

- [ ] **Step 4: Run pipeline test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_watchlist_pipeline.WatchlistPipelineTests -v
```

Expected: PASS.

## Task 6: README Usage and Smoke Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add usage docs**

Append a short section:

## 观察标的执行策略

示例配置：

```bash
.venv/bin/python scripts/run_watchlist_strategy.py \
  --config config/watchlist.example.json \
  --start-date 20251101 \
  --end-date 20260427 \
  --mode close_confirmed \
  --output-dir tmp/watchlist_robot
```

盘中模式：

```bash
.venv/bin/python scripts/run_watchlist_strategy.py \
  --config config/watchlist.example.json \
  --start-date 20251101 \
  --end-date 20260427 \
  --mode intraday \
  --output-dir tmp/watchlist_robot_intraday
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_watchlist_config \
  tests.test_watchlist_signals \
  tests.test_watchlist_pipeline \
  tests.test_realtime_quote_sources \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run CLI smoke in cache-friendly mode**

Run:

```bash
.venv/bin/python scripts/run_watchlist_strategy.py \
  --config config/watchlist.example.json \
  --start-date 20251101 \
  --end-date 20260427 \
  --mode close_confirmed \
  --output-dir tmp/watchlist_smoke
```

Expected:

- `tmp/watchlist_smoke/watchlist_report.json` exists.
- `tmp/watchlist_smoke/watchlist_report.csv` exists.
- `tmp/watchlist_smoke/watchlist_report.md` exists.

## Self-Review

- Spec coverage: Plan covers input config, historical data, intraday realtime quotes, signal groups, scoring, JSON/CSV/Markdown output, and CLI execution.
- Placeholder scan: The plan uses concrete file paths, commands, functions, and expected results.
- Type consistency: The plan consistently uses `WatchlistConfig`, `WatchSymbol`, `SignalResult`, `evaluate_symbol()`, `write_reports()`, and `run_watchlist_strategy()`.
