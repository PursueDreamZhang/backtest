# Price Touch T+1 Backtest Design

## Goal

为 `watchlist_backtest` 增加一套独立的“价格触达成交 + A 股 T+1 止损”回测模式，用日线 `open/high/low/close` 近似盘中盯盘交易：

- 前一交易日收盘后先确定候选 setup、`trigger_price`、`stop_loss`
- 下一交易日若价格区间触达 `trigger_price`，则按该价格成交
- 买入当日不允许止损
- 从下一交易日开始，按开盘价优先、盘中止损价次之的顺序执行止损

这套模式必须与现有“收盘确认信号，次日开盘买入”的回测模式并存，方便横向比较。

## Non-Goals

- 不改动现有默认回测模式的行为与结果
- 不引入分时级别数据
- 不恢复或近似回测当日量能确认逻辑
- 不在本次设计中修改观察池 HTML 报告结构

## Current Behavior

当前回测链路如下：

- `scripts/backtest_watchlist_strategy.py` 调用 `watchlist_backtest.engine.run_watchlist_backtest`
- `watchlist_backtest.signal_diary.build_signal_diary` 固定以 `mode="close_confirmed"` 生成每日信号
- `watchlist_backtest.engine` 使用前一交易日的 `触发买点` 信号
- 若下一交易日 `open` 存在，且开盘价距离止损位不超过风控阈值，则按下一交易日 `open` 买入

当前系统没有显式的 `trigger_price` 字段，也没有“区间触价成交”逻辑。

## Proposed Mode

新增一个独立模式，名称建议为 `price_touch_tplus1`。

该模式下：

1. 信号日 `T-1`：
   - 使用 `T-1` 收盘后可知的数据，计算 setup、`stop_loss`、`trigger_price`
   - 仅保留 `group == "触发买点"` 的候选

2. 交易日 `T`：
   - 若 `low <= trigger_price <= high`，则视为盘中可成交
   - 成交价固定记为 `trigger_price`
   - 若未触达，则该信号在 `T` 不成交

3. 持仓日 `T`：
   - 当日禁止止损，符合 A 股 `T+1`

4. 持仓日 `T+1` 及之后：
   - 若 `open <= stop_loss`，按 `open` 止损
   - 否则若 `low <= stop_loss`，按 `stop_loss` 止损
   - 否则继续沿用现有排除观察、超持有天数等退出逻辑

## Trigger Price Formulas

本次由用户明确指定 4 个 setup 的触发价口径如下：

### 1. `MA40 弹簧压紧后松开`

- `trigger_price = previous_close * 1.05`
- 其中 `previous_close` 为信号日 `T-1` 的收盘价

### 2. `MA20 第一次回档`

- `trigger_price = MA20`
- 使用 **信号日 `T-1` 收盘后可知的 MA20 值**
- 不使用交易日 `T` 收盘后才完整形成的 MA20，避免未来函数

### 3. `整理后第一根启动阳线`

- `trigger_price = previous_close * 1.05`

### 4. `双底或二次压紧`

- `trigger_price = previous_close * 1.05`

## Trigger Price Availability

只有满足以下条件时，信号日才可生成有效 `trigger_price`：

- `group == "触发买点"`
- 触发价公式依赖的字段存在且为有限数值
- `stop_loss` 存在且为有限数值

若某条候选信号无法计算 `trigger_price`，则：

- 保留该信号日记记录
- 在回测开仓阶段跳过该候选
- 便于后续在报告或调试中识别“模型触发但缺失触发价”的情况

## Entry Rules

在 `price_touch_tplus1` 模式下，开仓规则为：

1. 只处理前一交易日 `T-1` 的候选信号
2. 读取交易日 `T` 的 `high/low`
3. 如果 `trigger_price` 落在 `[low, high]` 区间内，则允许成交
4. 成交价格固定为 `trigger_price`
5. 若触发价未落入区间，则当日不成交

### Risk Guardrail

现有开仓风控基于“次日开盘价距离止损位过远则拒绝成交”。新模式下应改为：

- 用 `trigger_price` 计算 `risk_to_stop_pct`
- 若 `trigger_price / stop_loss - 1` 超过现有阈值（默认 `12%`），则拒绝成交

这样可以复用现有风控口径，只是把参考价格从 `next_open_price` 换成 `trigger_price`。

## Same-Day Buy And Stop Interaction

用户已明确：

- A 股是 `T+1`
- 买入当天不允许止损

因此在新模式下：

- 即使交易日 `T` 的 `low-high` 区间同时覆盖了 `trigger_price` 和 `stop_loss`
- 仍然视为 **成交成功且当日不止损**
- 最早从 `T+1` 才开始检查止损

## Exit Rules

新模式只改止损优先级，不改其他退出口径：

### Stop Loss

从持仓次日开始：

1. 若 `open <= stop_loss`，按 `open` 退出
2. 否则若 `low <= stop_loss`，按 `stop_loss` 退出
3. 否则继续持有

### Existing Exit Rules To Preserve

以下逻辑继续保留：

- 若最新信号变为 `排除观察`，则按现有逻辑退出
- 若持有天数达到 `max_hold_days`，则按现有逻辑退出

但这些规则的执行顺序应放在“买入次日起的止损判断”之后，以保持风险优先。

## Data Model Changes

建议在信号日记 DataFrame 中新增以下字段：

- `trigger_price`
- `trigger_price_rule`

用途：

- `trigger_price`：回测实际使用的数值触发价
- `trigger_price_rule`：便于调试与报告追踪，例如：
  - `prev_close_x_1.05`
  - `signal_day_ma20`

这些字段应出现在：

- `signal_diary.csv`
- 回测引擎内存中的 diary DataFrame

是否在 HTML 报告中展示可作为后续增强，本次不是必需项。

## Code Changes

### `watchlist_backtest/signal_diary.py`

- 在生成日记行时，为 `group == "触发买点"` 的 setup 计算 `trigger_price`
- 触发价计算必须只依赖信号日当时可知的数据
- 将 `trigger_price` 和 `trigger_price_rule` 写入 diary

### `watchlist_backtest/rules.py`

- 保留现有开仓判断函数，供老模式继续使用
- 新增适用于 `price_touch_tplus1` 的开仓判断函数，例如：
  - 判断是否区间触价
  - 判断触发价距离止损位是否过远
- 新增适用于 `T+1` 止损的退出判断分支

### `watchlist_backtest/engine.py`

- 为 `run_watchlist_backtest` 增加 `mode` 参数
- 老模式保持现状
- 新模式下：
  - 用前一交易日信号 + 当日 `high/low` 判断是否成交
  - 成交价使用 `trigger_price`
  - 记录买入日后首日不可止损
  - 从下一交易日开始按新止损顺序处理退出

### `scripts/backtest_watchlist_strategy.py`

- 增加 `--mode` 参数
- 至少支持：
  - `close_confirmed`
  - `price_touch_tplus1`

## Backward Compatibility

- 若未指定 `--mode`，默认仍使用当前回测口径
- 现有测试、历史输出目录、已有回测结果应保持不变
- 新模式输出建议使用单独目录，避免覆盖老结果

## Testing

需要补充或调整以下测试：

### Signal Diary

- 为 4 个 setup 分别验证 `trigger_price` 计算正确
- 验证 `MA20 第一次回档` 使用的是信号日可知的 MA20，而不是交易日收盘后的值

### Entry Rules

- 当 `low <= trigger_price <= high` 时成功成交
- 当区间未触达 `trigger_price` 时不成交
- 当 `trigger_price` 距离 `stop_loss` 过远时拒绝成交

### Exit Rules

- 买入当天即使 `low <= stop_loss` 也不止损
- 次日 `open <= stop_loss` 时按 `open` 止损
- 次日 `open > stop_loss` 且 `low <= stop_loss` 时按 `stop_loss` 止损

### Regression Coverage

- 现有默认模式测试继续通过
- 新模式不会改变旧模式下的成交笔数与报表结构

## Acceptance Criteria

- 能通过参数切换运行新旧两套回测模式
- 新模式可为 4 个指定 setup 生成符合约定的 `trigger_price`
- 交易日价格区间触达 `trigger_price` 时按该价成交
- 买入当日不止损，次日起按 `open` 优先的 T+1 规则止损
- 默认模式结果保持不变

## Open Questions

本轮已确认并固定以下口径，因此当前无阻塞性开放问题：

- `MA20 第一次回档` 使用信号日可知的 MA20
- 其余 3 个 setup 使用前一日收盘价 `* 1.05`
- 买入当日不止损，次日起按 T+1 规则处理
