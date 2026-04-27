# Research-first 市场阶段与主线 ETF 研究项目

这个仓库当前以 **research 层** 为主工程，核心目标是做：

- ETF universe 管理
- 横截面特征提取
- 主线 ETF 排名
- 市场阶段识别
- 开仓 gating 信号输出
- 后续研究验证闭环

旧的 Backtrader 回测、参数优化与趋势策略代码仍然保留，但已经被降级为 **legacy 示例代码**，不再作为项目主路径。

## 当前主路径

### 研究入口

```bash
python3 scripts/research_market_states.py \
  --universe config/etf_universe.example.json \
  --start-date 20220101 \
  --end-date 20261231 \
  --output-dir tmp/market_regime
```

### 研究输出

- `daily_state.csv`：日度市场阶段和可开仓信号
- `leaderboard.csv`：每日 ETF 排行榜
- `summary.json`：阶段与信号统计汇总

### 结果可视化出图

研究结果跑完后，可以基于同一个 `output-dir` 直接生成交互式行情阶段图：

```bash
.venv/bin/python scripts/render_market_regime_dashboard.py \
  --universe config/etf_universe.example.json \
  --result-dir tmp/market_regime
```

生成文件：

- `market_regime_dashboard.html`：交互式市场阶段可视化页面

当前出图规则：

- X 轴按交易日绘制，不按自然日留空
- 背景按 `启动 / 主升 / 混沌 / 退潮` 分阶段着色
- 市场代表 ETF 默认显示，行业 ETF 默认隐藏，但都可以在图例里单独显示或隐藏
- 鼠标悬停会显示日期、当天阶段和 ETF 的归一化净值

缓存规则：

- 默认是 `cache-only`，只读取本地缓存和本次研究结果，不会为了出图再联网补数据
- 适合“研究已经跑完，只想重画图”的场景
- 如果缓存缺失，脚本会直接报错，避免偷偷触发远程数据源

如果你明确要刷新价格数据，再手动加：

```bash
.venv/bin/python scripts/render_market_regime_dashboard.py \
  --universe config/etf_universe.example.json \
  --result-dir tmp/market_regime \
  --refresh-data
```

`--refresh-data` 会允许数据层按当前区间补齐或刷新缓存，这种模式更适合你主动想更新到最新价格时使用。

## 观察标的执行策略

观察标的执行策略用于读取你给出的方向和标的池，结合最近半年日线行情和可选实时行情，输出 `触发买点 / 重点观察 / 等待回调 / 排除观察` 或盘中对应分组。

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

生成文件：

- `watchlist_report.json`：结构化结果
- `watchlist_report.csv`：表格结果
- `watchlist_report.md`：可读摘要

## research 模块

- `research/settings.py`：研究参数与数据源优先级
- `research/data_loader.py`：研究层批量数据加载
- `research/pipeline.py`：研究主流程
- `research/market_regime.py`：特征、排名、市场阶段与汇总
- `research/etf_universe.py`：ETF universe 加载

## legacy 模块

以下代码已经迁入 `legacy/backtrader_examples/`，作为旧版 demo 与兼容示例保留：

- `main.py`
- `optimize.py`
- `trend_strategy.py`
- `strategies/`
- `docs/trend_following_logic.md`

根目录同名文件现在是兼容入口，会转发到 `legacy` 目录中的实现。

## 说明

这次改造优先实现了 **research-first 的工程主线**：

- 研究脚本改为调用 `research.pipeline.run_research`
- 研究层拥有自己的 `settings.py` 与 `data_loader.py`
- `build_leaderboard()` 改为优先读取研究配置中的权重
- 旧回测逻辑迁入 `legacy/`，根目录保留兼容包装入口

如果你后续还想继续做物理清理，可以再把根目录遗留的旧 `strategies/` 等目录删除，但当前版本已经可以直接以 research 作为主工程继续演进。
