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
