# 量化回测框架（Backtrader）

当前项目已统一为“模块化入口 + 单一策略实现”，避免旧版脚本和新版目录结构并存导致的维护问题。

## 当前目录结构

```text
backtest/
├── main.py                     # 回测主入口
├── optimize.py                 # 参数优化入口
├── config.py                   # 回测与策略参数
├── trend_strategy.py           # 兼容层（旧接口转发到新模块）
├── strategies/
│   ├── trend_following.py      # 趋势策略（唯一实现）
│   ├── sma.py
│   ├── rsi.py
│   └── base.py
└── data/
    ├── sina_source.py          # 新浪数据源（含缓存）
    └── mock_source.py          # 模拟数据源
```

## 安装依赖

```bash
pip3 install backtrader pandas requests numpy
```

## 快速开始

### 1) 运行回测

```bash
python3 main.py
```

或在代码中：

```python
from main import run_backtest

run_backtest(symbol='002149', start_date='20200101', end_date='20260402', use_mock=False)
```

### 2) 参数优化

```bash
python3 optimize.py
```

或在代码中：

```python
from optimize import optimize_strategy

results = optimize_strategy(
    symbol='002149',
    breakout_range=(0.04, 0.05, 0.06),
    hold_days_range=(2, 3, 4),
)
```

## 配置说明

- 回测参数：`config.py` 中 `BACKTEST_CONFIG`
- 策略参数：`config.py` 中 `TREND_FOLLOWING_PARAMS`

## 策略逻辑说明

- 趋势跟踪策略的买入、卖出、仓位控制与整体思路说明见：`docs/trend_following_logic.md`

## 兼容说明

- 保留了 `trend_strategy.py`，用于兼容旧调用路径。
- 新增功能与修复优先在 `main.py` / `optimize.py` / `strategies/` / `data/` 维护。

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
- `leaderboard.csv`：每日 ETF 排行榜
- `summary.json`：阶段与信号统计汇总
