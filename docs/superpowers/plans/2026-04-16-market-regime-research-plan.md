# Market Regime Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一套基于 ETF 代理池的离线研究层，输出市场阶段、主线 ETF 前 3、退潮风险和是否适合开新仓的日度结果与汇总统计。

**Architecture:** 新增独立的 `research/` 模块，负责 ETF 代理池配置加载、ETF 特征与加权分数计算、市场阶段映射和结果汇总；通过独立脚本复用现有 `FallbackDataSource` 拉取 ETF 日线并导出 `daily_state.csv`、`leaderboard.csv` 和 `summary.json`。研究层先与 Backtrader 解耦，后续如需接交易层，只复用 `research/market_regime.py` 的输出。

**Tech Stack:** Python 3.13, pandas, numpy, unittest/pytest, 现有 `FallbackDataSource`

---

## File Structure

```text
/Users/zhangchunfu/Nutstore Files/code/backtest/
├── config.py                                     # 修改：新增研究参数默认值
├── README.md                                     # 修改：新增研究脚本用法
├── config/
│   └── etf_universe.example.json                 # 新建：ETF 代理池配置样例
├── research/
│   ├── __init__.py                               # 新建：导出研究模块 API
│   ├── etf_universe.py                           # 新建：ETF 代理池配置加载
│   └── market_regime.py                          # 新建：分数、阶段、汇总逻辑
├── scripts/
│   └── research_market_states.py                 # 新建：命令行研究入口
└── tests/
    ├── test_etf_universe.py                      # 新建：代理池配置加载测试
    ├── test_market_regime.py                     # 新建：评分、阶段和汇总测试
    └── test_research_market_states.py            # 新建：脚本导出结果测试
```

---

### Task 1: ETF 代理池配置与加载器

**Files:**
- Create: `/Users/zhangchunfu/Nutstore Files/code/backtest/config/etf_universe.example.json`
- Create: `/Users/zhangchunfu/Nutstore Files/code/backtest/research/__init__.py`
- Create: `/Users/zhangchunfu/Nutstore Files/code/backtest/research/etf_universe.py`
- Create: `/Users/zhangchunfu/Nutstore Files/code/backtest/tests/test_etf_universe.py`
- Modify: `/Users/zhangchunfu/Nutstore Files/code/backtest/config.py`

- [ ] **Step 1: 写 ETF 代理池配置加载失败测试**

```python
import json
import tempfile
import unittest

from research.etf_universe import EtfUniverseEntry, load_etf_universe


class TestEtfUniverse(unittest.TestCase):
    def test_should_load_entries_and_split_market_and_theme_flags(self):
        payload = {
            'etfs': [
                {
                    'symbol': '510300',
                    'name': '沪深300ETF',
                    'tags': ['宽基', '大盘'],
                    'is_market_proxy': True,
                    'is_theme_proxy': False,
                },
                {
                    'symbol': '512480',
                    'name': '半导体ETF',
                    'tags': ['科技', '半导体'],
                    'is_market_proxy': False,
                    'is_theme_proxy': True,
                },
            ]
        }

        with tempfile.NamedTemporaryFile('w+', suffix='.json', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
            f.flush()

            result = load_etf_universe(f.name)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], EtfUniverseEntry(
            symbol='510300',
            name='沪深300ETF',
            tags=('宽基', '大盘'),
            is_market_proxy=True,
            is_theme_proxy=False,
        ))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_etf_universe.py -q`
Expected: FAIL，提示 `ModuleNotFoundError: No module named 'research'` 或 `cannot import name 'load_etf_universe'`

- [ ] **Step 3: 创建 ETF 代理池样例配置**

```json
{
  "etfs": [
    {
      "symbol": "510300",
      "name": "沪深300ETF",
      "tags": ["宽基", "大盘"],
      "is_market_proxy": true,
      "is_theme_proxy": false
    },
    {
      "symbol": "512100",
      "name": "中证1000ETF",
      "tags": ["宽基", "中小盘"],
      "is_market_proxy": true,
      "is_theme_proxy": false
    },
    {
      "symbol": "159915",
      "name": "创业板ETF",
      "tags": ["成长", "创业板"],
      "is_market_proxy": true,
      "is_theme_proxy": false
    },
    {
      "symbol": "512480",
      "name": "半导体ETF",
      "tags": ["科技", "半导体"],
      "is_market_proxy": false,
      "is_theme_proxy": true
    },
    {
      "symbol": "512010",
      "name": "医药ETF",
      "tags": ["医药"],
      "is_market_proxy": false,
      "is_theme_proxy": true
    },
    {
      "symbol": "512660",
      "name": "军工ETF",
      "tags": ["军工"],
      "is_market_proxy": false,
      "is_theme_proxy": true
    }
  ]
}
```

- [ ] **Step 4: 实现代理池加载模块和导出**

```python
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class EtfUniverseEntry:
    symbol: str
    name: str
    tags: tuple[str, ...]
    is_market_proxy: bool
    is_theme_proxy: bool


def load_etf_universe(path: str | Path) -> list[EtfUniverseEntry]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    items = payload.get('etfs', [])
    result: list[EtfUniverseEntry] = []
    for item in items:
        result.append(
            EtfUniverseEntry(
                symbol=str(item['symbol']).strip(),
                name=str(item['name']).strip(),
                tags=tuple(item.get('tags', [])),
                is_market_proxy=bool(item.get('is_market_proxy', False)),
                is_theme_proxy=bool(item.get('is_theme_proxy', True)),
            )
        )
    return result
```

```python
from .etf_universe import EtfUniverseEntry, load_etf_universe

__all__ = ['EtfUniverseEntry', 'load_etf_universe']
```

- [ ] **Step 5: 在 `config.py` 增加研究参数默认值**

```python
MARKET_REGIME_PARAMS = {
    'benchmark_windows': [10, 20],
    'relative_strength_windows': [20, 40, 60],
    'momentum_windows': [5, 10, 20],
    'short_ma': 20,
    'long_ma': 40,
    'short_volume_window': 5,
    'long_volume_window': 20,
    'forward_windows': [5, 10, 20],
    'weights': {
        'relative_strength': 0.30,
        'momentum': 0.25,
        'volume_price': 0.25,
        'trend_support': 0.10,
        'stability': 0.10,
    },
    'market_weights': {
        'trend': 0.25,
        'breadth': 0.25,
        'volume_confirmation': 0.25,
        'cooldown_risk': 0.25,
    },
}
```

- [ ] **Step 6: 再跑测试，确认通过**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_etf_universe.py -q`
Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
git add /Users/zhangchunfu/Nutstore\ Files/code/backtest/config.py \
        /Users/zhangchunfu/Nutstore\ Files/code/backtest/config/etf_universe.example.json \
        /Users/zhangchunfu/Nutstore\ Files/code/backtest/research/__init__.py \
        /Users/zhangchunfu/Nutstore\ Files/code/backtest/research/etf_universe.py \
        /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_etf_universe.py
git commit -m "feat: add etf proxy universe config loader"
```

---

### Task 2: ETF 评分与排行榜核心逻辑

**Files:**
- Create: `/Users/zhangchunfu/Nutstore Files/code/backtest/research/market_regime.py`
- Create: `/Users/zhangchunfu/Nutstore Files/code/backtest/tests/test_market_regime.py`

- [ ] **Step 1: 写 ETF 排行分测试**

```python
import unittest
import pandas as pd

from research.market_regime import build_feature_table, build_leaderboard


def _frame(values, volumes):
    idx = pd.date_range('2026-01-01', periods=len(values), freq='B')
    return pd.DataFrame(
        {
            'open': values,
            'high': [x * 1.01 for x in values],
            'low': [x * 0.99 for x in values],
            'close': values,
            'volume': volumes,
        },
        index=idx,
    )


class TestMarketRegimeScores(unittest.TestCase):
    def test_should_rank_semiconductor_etf_first_when_relative_strength_and_volume_are_strongest(self):
        frames = {
            '510300': _frame([100 + i * 0.3 for i in range(80)], [1000] * 80),
            '512480': _frame([100 + i * 0.8 for i in range(80)], [900 + i * 8 for i in range(80)]),
            '512010': _frame([100 + i * 0.2 for i in range(80)], [1000] * 80),
        }
        params = {
            'relative_strength_windows': [20, 40, 60],
            'momentum_windows': [5, 10, 20],
            'short_ma': 20,
            'long_ma': 40,
            'short_volume_window': 5,
            'long_volume_window': 20,
            'weights': {
                'relative_strength': 0.30,
                'momentum': 0.25,
                'volume_price': 0.25,
                'trend_support': 0.10,
                'stability': 0.10,
            },
        }

        features = build_feature_table(frames, benchmark_symbol='510300', params=params)
        leaderboard = build_leaderboard(features)
        last_day = leaderboard['date'].max()
        top1 = leaderboard.loc[leaderboard['date'] == last_day].sort_values('rank').iloc[0]

        self.assertEqual(top1['symbol'], '512480')
        self.assertEqual(int(top1['rank']), 1)
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_market_regime.py -q`
Expected: FAIL，提示 `cannot import name 'build_feature_table'`

- [ ] **Step 3: 实现特征表与排行榜的最小版本**

```python
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def _pct_return(series: pd.Series, window: int) -> pd.Series:
    return series / series.shift(window) - 1.0


def build_feature_table(frames: dict[str, pd.DataFrame], benchmark_symbol: str, params: dict[str, Any]) -> pd.DataFrame:
    benchmark = frames[benchmark_symbol].copy().sort_index()
    benchmark_returns = {
        window: _pct_return(benchmark['close'], window)
        for window in params['relative_strength_windows']
    }

    rows: list[dict[str, Any]] = []
    for symbol, df in frames.items():
        work = df.copy().sort_index()
        work['ma_short'] = work['close'].rolling(params['short_ma']).mean()
        work['ma_long'] = work['close'].rolling(params['long_ma']).mean()
        work['vol_short'] = work['volume'].rolling(params['short_volume_window']).mean()
        work['vol_long'] = work['volume'].rolling(params['long_volume_window']).mean()

        for date in work.index:
            row = {'date': date, 'symbol': symbol}
            rs_values = []
            for window in params['relative_strength_windows']:
                own = benchmark_returns[window].reindex(work.index)
                rel = _pct_return(work['close'], window).reindex(work.index) - own
                row[f'rs_{window}'] = rel.loc[date]
                rs_values.append(rel.loc[date])
            row['relative_strength_score'] = np.nanmean(rs_values)

            mom_values = []
            for window in params['momentum_windows']:
                val = _pct_return(work['close'], window).loc[date]
                row[f'mom_{window}'] = val
                mom_values.append(val)
            row['momentum_score'] = np.nanmean(mom_values)

            vol_ratio = work['vol_short'].loc[date] / work['vol_long'].loc[date] if work['vol_long'].loc[date] else np.nan
            row['volume_price_score'] = vol_ratio
            row['trend_support_score'] = float(
                work['close'].loc[date] > work['ma_short'].loc[date]
            ) + float(work['ma_short'].loc[date] > work['ma_long'].loc[date])
            row['stability_score'] = 0.0
            rows.append(row)

    feature_table = pd.DataFrame(rows).dropna().sort_values(['date', 'symbol'])
    return feature_table


def build_leaderboard(feature_table: pd.DataFrame) -> pd.DataFrame:
    work = feature_table.copy()
    work['relative_strength_score'] = work.groupby('date')['relative_strength_score'].rank(pct=True)
    work['momentum_score'] = work.groupby('date')['momentum_score'].rank(pct=True)
    work['volume_price_score'] = work.groupby('date')['volume_price_score'].rank(pct=True)
    work['trend_support_score'] = work.groupby('date')['trend_support_score'].rank(pct=True)
    work['stability_score'] = work.groupby('date')['stability_score'].rank(pct=True)

    work['composite_score'] = (
        work['relative_strength_score'] * 0.30
        + work['momentum_score'] * 0.25
        + work['volume_price_score'] * 0.25
        + work['trend_support_score'] * 0.10
        + work['stability_score'] * 0.10
    )
    work['rank'] = work.groupby('date')['composite_score'].rank(method='first', ascending=False)
    work['is_leader_candidate'] = work['rank'] <= 3
    return work
```

- [ ] **Step 4: 再跑测试，确认通过**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_market_regime.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add /Users/zhangchunfu/Nutstore\ Files/code/backtest/research/market_regime.py \
        /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_market_regime.py
git commit -m "feat: add etf scoring and leaderboard core"
```

---

### Task 3: 市场阶段、退潮和可开仓信号

**Files:**
- Modify: `/Users/zhangchunfu/Nutstore Files/code/backtest/research/market_regime.py`
- Modify: `/Users/zhangchunfu/Nutstore Files/code/backtest/tests/test_market_regime.py`

- [ ] **Step 1: 写阶段映射和开仓信号测试**

```python
    def test_should_mark_market_as_rally_when_breadth_volume_and_leader_gap_are_all_strong(self):
        frames = {
            '510300': _frame([100 + i * 0.3 for i in range(100)], [1000] * 100),
            '512480': _frame([100 + i * 0.8 for i in range(100)], [1200 + i * 10 for i in range(100)]),
            '512010': _frame([100 + i * 0.5 for i in range(100)], [1100 + i * 8 for i in range(100)]),
            '512660': _frame([100 + i * 0.45 for i in range(100)], [1080 + i * 8 for i in range(100)]),
        }
        params = {
            'relative_strength_windows': [20, 40, 60],
            'momentum_windows': [5, 10, 20],
            'short_ma': 20,
            'long_ma': 40,
            'short_volume_window': 5,
            'long_volume_window': 20,
            'weights': {
                'relative_strength': 0.30,
                'momentum': 0.25,
                'volume_price': 0.25,
                'trend_support': 0.10,
                'stability': 0.10,
            },
            'market_weights': {
                'trend': 0.25,
                'breadth': 0.25,
                'volume_confirmation': 0.25,
                'cooldown_risk': 0.25,
            },
        }

        features = build_feature_table(frames, benchmark_symbol='510300', params=params)
        leaderboard = build_leaderboard(features)
        daily_state = build_daily_state(frames, leaderboard, benchmark_symbol='510300', params=params)

        last_day = daily_state.iloc[-1]
        self.assertEqual(last_day['market_stage'], '主升')
        self.assertTrue(bool(last_day['can_open_new_position']))
        self.assertEqual(last_day['leader_etf_top1'], '512480')
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_market_regime.py -q`
Expected: FAIL，提示 `cannot import name 'build_daily_state'`

- [ ] **Step 3: 实现日度状态映射**

```python
def build_daily_state(
    frames: dict[str, pd.DataFrame],
    leaderboard: pd.DataFrame,
    benchmark_symbol: str,
    params: dict[str, Any],
) -> pd.DataFrame:
    benchmark = frames[benchmark_symbol].copy().sort_index()
    benchmark['ma_short'] = benchmark['close'].rolling(params['short_ma']).mean()
    benchmark['ma_long'] = benchmark['close'].rolling(params['long_ma']).mean()
    benchmark['ret_10'] = benchmark['close'].pct_change(10)
    benchmark['ret_20'] = benchmark['close'].pct_change(20)
    benchmark['dd_10'] = benchmark['close'] / benchmark['close'].rolling(10).max() - 1.0

    states = []
    for date, group in leaderboard.groupby('date'):
        top = group.sort_values('rank').head(3)
        breadth_close_above_short = float((group['trend_support_score'] > 0).mean())
        volume_confirmation = float((group['volume_price_score'] > 0.5).mean())
        trend_score = float(
            (benchmark.loc[date, 'close'] > benchmark.loc[date, 'ma_short'])
            + (benchmark.loc[date, 'ma_short'] > benchmark.loc[date, 'ma_long'])
        ) / 2.0
        cooldown_risk = float(abs(min(benchmark.loc[date, 'dd_10'], 0.0)))
        leader_gap = float(top.iloc[0]['composite_score'] - top.iloc[1]['composite_score']) if len(top) > 1 else 0.0
        leader_stability = float(top['symbol'].nunique() <= 3)
        market_stage_score = (
            trend_score * params['market_weights']['trend']
            + breadth_close_above_short * params['market_weights']['breadth']
            + volume_confirmation * params['market_weights']['volume_confirmation']
            + (1.0 - cooldown_risk) * params['market_weights']['cooldown_risk']
        )

        if market_stage_score >= 0.75 and cooldown_risk < 0.08:
            stage = '主升'
        elif market_stage_score >= 0.60 and cooldown_risk < 0.12:
            stage = '启动'
        elif cooldown_risk >= 0.15:
            stage = '退潮'
        else:
            stage = '混沌'

        can_open = stage in {'启动', '主升'} and leader_gap > 0.02
        states.append(
            {
                'date': date,
                'market_stage': stage,
                'market_stage_score': market_stage_score,
                'market_trend_score': trend_score,
                'market_breadth_score': breadth_close_above_short,
                'volume_confirmation_score': volume_confirmation,
                'cooldown_risk_score': cooldown_risk,
                'leader_etf_top1': top.iloc[0]['symbol'],
                'leader_etf_top2': top.iloc[1]['symbol'] if len(top) > 1 else None,
                'leader_etf_top3': top.iloc[2]['symbol'] if len(top) > 2 else None,
                'leader_strength_score': float(top.iloc[0]['composite_score']),
                'leader_gap_score': leader_gap,
                'leader_stability_score': leader_stability,
                'can_open_new_position': can_open,
                'open_position_reason': 'stage_ok_and_leader_gap_positive' if can_open else 'stage_or_leader_gap_not_enough',
            }
        )
    return pd.DataFrame(states).sort_values('date').reset_index(drop=True)
```

- [ ] **Step 4: 再跑测试，确认通过**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_market_regime.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add /Users/zhangchunfu/Nutstore\ Files/code/backtest/research/market_regime.py \
        /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_market_regime.py
git commit -m "feat: add market stage and can-open signals"
```

---

### Task 4: 汇总报告与研究脚本入口

**Files:**
- Create: `/Users/zhangchunfu/Nutstore Files/code/backtest/scripts/research_market_states.py`
- Create: `/Users/zhangchunfu/Nutstore Files/code/backtest/tests/test_research_market_states.py`
- Modify: `/Users/zhangchunfu/Nutstore Files/code/backtest/research/market_regime.py`

- [ ] **Step 1: 写脚本导出测试**

```python
import json
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

from scripts.research_market_states import run_research


def _frame(base_step):
    idx = pd.date_range('2026-01-01', periods=90, freq='B')
    values = [100 + i * base_step for i in range(90)]
    return pd.DataFrame(
        {
            'open': values,
            'high': [x * 1.01 for x in values],
            'low': [x * 0.99 for x in values],
            'close': values,
            'volume': [1000 + i * 5 for i in range(90)],
        },
        index=idx,
    )


class TestResearchMarketStates(unittest.TestCase):
    def test_should_export_daily_state_leaderboard_and_summary(self):
        universe = {
            'etfs': [
                {'symbol': '510300', 'name': '沪深300ETF', 'tags': ['宽基'], 'is_market_proxy': True, 'is_theme_proxy': False},
                {'symbol': '512480', 'name': '半导体ETF', 'tags': ['科技'], 'is_market_proxy': False, 'is_theme_proxy': True},
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            universe_path = os.path.join(tmpdir, 'universe.json')
            with open(universe_path, 'w', encoding='utf-8') as f:
                json.dump(universe, f, ensure_ascii=False)

            output_dir = os.path.join(tmpdir, 'out')

            fake_frames = {
                '510300': _frame(0.3),
                '512480': _frame(0.8),
            }

            with mock.patch('scripts.research_market_states.load_symbol_frames', return_value=fake_frames):
                result = run_research(
                    universe_path=universe_path,
                    output_dir=output_dir,
                    start_date='20260101',
                    end_date='20260630',
                )

            self.assertTrue(os.path.exists(result['daily_state_path']))
            self.assertTrue(os.path.exists(result['leaderboard_path']))
            self.assertTrue(os.path.exists(result['summary_path']))
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_research_market_states.py -q`
Expected: FAIL，提示 `ModuleNotFoundError` 或 `cannot import name 'run_research'`

- [ ] **Step 3: 为 `market_regime.py` 增加汇总函数**

```python
def build_summary(daily_state: pd.DataFrame, leaderboard: pd.DataFrame, benchmark_frame: pd.DataFrame, forward_windows: list[int]) -> dict[str, Any]:
    benchmark = benchmark_frame[['close']].copy().sort_index()
    summary: dict[str, Any] = {'stages': {}, 'open_signal': {}, 'leader_switch_count': 0}

    top1_series = daily_state['leader_etf_top1'].fillna('')
    summary['leader_switch_count'] = int((top1_series != top1_series.shift(1)).sum())

    for stage, group in daily_state.groupby('market_stage'):
        summary['stages'][stage] = {'count': int(len(group))}

    for flag, group in daily_state.groupby('can_open_new_position'):
        summary['open_signal'][str(bool(flag))] = {'count': int(len(group))}

    return summary
```

- [ ] **Step 4: 实现研究脚本入口**

```python
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from config import BACKTEST_CONFIG, MARKET_REGIME_PARAMS
from data.fallback_source import FallbackDataSource
from research.etf_universe import load_etf_universe
from research.market_regime import build_feature_table, build_leaderboard, build_daily_state, build_summary


def load_symbol_frames(symbols: list[str], start_date: str, end_date: str):
    priority = BACKTEST_CONFIG.get('data_source_priority', ['tushare', 'sina', 'akshare', 'yfinance'])
    source = FallbackDataSource(priority=priority)
    frames = {}
    for symbol in symbols:
        frames[symbol] = source.get_data(symbol, start_date, end_date, use_cache=True)
    return frames


def run_research(universe_path: str, output_dir: str, start_date: str, end_date: str):
    universe = load_etf_universe(universe_path)
    symbols = [item.symbol for item in universe]
    market_proxies = [item.symbol for item in universe if item.is_market_proxy]
    benchmark_symbol = market_proxies[0]

    frames = load_symbol_frames(symbols, start_date, end_date)
    features = build_feature_table(frames, benchmark_symbol=benchmark_symbol, params=MARKET_REGIME_PARAMS)
    leaderboard = build_leaderboard(features)
    daily_state = build_daily_state(frames, leaderboard, benchmark_symbol=benchmark_symbol, params=MARKET_REGIME_PARAMS)
    summary = build_summary(daily_state, leaderboard, frames[benchmark_symbol], MARKET_REGIME_PARAMS['forward_windows'])

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    daily_state_path = output / 'daily_state.csv'
    leaderboard_path = output / 'leaderboard.csv'
    summary_path = output / 'summary.json'

    daily_state.to_csv(daily_state_path, index=False)
    leaderboard.to_csv(leaderboard_path, index=False)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'daily_state_path': str(daily_state_path),
        'leaderboard_path': str(leaderboard_path),
        'summary_path': str(summary_path),
    }
```

- [ ] **Step 5: 再跑测试，确认通过**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_research_market_states.py -q`
Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add /Users/zhangchunfu/Nutstore\ Files/code/backtest/research/market_regime.py \
        /Users/zhangchunfu/Nutstore\ Files/code/backtest/scripts/research_market_states.py \
        /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_research_market_states.py
git commit -m "feat: add offline market regime research script"
```

---

### Task 5: README 使用说明与最终回归测试

**Files:**
- Modify: `/Users/zhangchunfu/Nutstore Files/code/backtest/README.md`

- [ ] **Step 1: 在 README 增加研究脚本用法**

```markdown
## 离线研究：市场阶段与主线ETF

### 运行研究脚本

```bash
python3 scripts/research_market_states.py \
  --universe config/etf_universe.example.json \
  --start-date 20220101 \
  --end-date 20261231 \
  --output-dir tmp/market_regime
```

### 输出文件

- `daily_state.csv`：日度市场阶段和可开仓信号
- `leaderboard.csv`：每日ETF排行榜
- `summary.json`：阶段与信号统计汇总
```

- [ ] **Step 2: 运行完整测试集**

Run: `pytest /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_etf_universe.py /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_market_regime.py /Users/zhangchunfu/Nutstore\ Files/code/backtest/tests/test_research_market_states.py -q`
Expected: 全部 PASS

- [ ] **Step 3: 手动运行研究脚本冒烟验证**

Run:

```bash
python3 /Users/zhangchunfu/Nutstore\ Files/code/backtest/scripts/research_market_states.py \
  --universe /Users/zhangchunfu/Nutstore\ Files/code/backtest/config/etf_universe.example.json \
  --start-date 20240101 \
  --end-date 20260415 \
  --output-dir /Users/zhangchunfu/Nutstore\ Files/code/backtest/tmp/market_regime
```

Expected:

- 生成 `daily_state.csv`
- 生成 `leaderboard.csv`
- 生成 `summary.json`
- 终端打印输出路径

- [ ] **Step 4: Commit**

```bash
git add /Users/zhangchunfu/Nutstore\ Files/code/backtest/README.md
git commit -m "docs: add market regime research usage"
```

---

## Self-Review

- **Spec coverage:** 本计划覆盖了规格中的 ETF 代理池配置、评分体系、阶段映射、主线前 3、可开仓信号、导出脚本和汇总报告。
- **Placeholder scan:** 计划中没有使用 `TODO`、`TBD` 或“稍后实现”类占位语句。
- **Type consistency:** `EtfUniverseEntry`、`build_feature_table`、`build_leaderboard`、`build_daily_state` 和 `run_research` 在各任务中的命名保持一致。

## 执行交接

计划已保存到 `docs/superpowers/plans/2026-04-16-market-regime-research-plan.md`。接下来有两种执行方式：

**1. 子代理协作执行（推荐）** - 我按任务逐个派发子代理执行，每个任务之间我做 review 和校正

**2. 当前会话直接实现** - 我在当前会话直接按计划实现、跑测试、修问题
