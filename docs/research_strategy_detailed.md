# Research 主策略详细说明

本文档用于详细说明当前版本项目中 `research` 层的主策略。目标不是只讲“策略思想”，而是让读者在阅读完本文档后，能够直接理解：

1. 程序从哪里启动。
2. 每个模块分别负责什么。
3. 数据是如何流入研究链路的。
4. 每一步产生什么中间结果。
5. 最终输出如何用于下游交易或继续研究。

当前仓库已经采用 **research-first** 结构，因此这里描述的是项目的主工程逻辑；旧的 Backtrader 回测与趋势策略现在只作为 `legacy/` 中的示例执行层存在，不再是仓库主路径。

---

## 一、主策略的定位

当前项目的核心不是“直接对某一只标的给买卖点”，而是一套 **上游研究决策系统**。它的主要任务是：

- 管理 ETF 研究对象（universe）
- 对 ETF 做横截面特征分析
- 每天识别更强的主线 ETF
- 判断市场当前处于什么阶段
- 给出是否允许开新仓的 gating 信号

所以，当前主策略真正回答的是三个问题：

1. **今天谁更强，谁像主线？**
2. **今天市场环境属于主升、启动、退潮还是混沌？**
3. **今天是否适合让下游策略开新仓？**

它更像一个“研究驱动的交易许可系统”，而不是一个直接执行买卖的交易脚本。

---

## 二、程序入口与主流程

### 1. 命令行入口

当前研究主入口是：

```bash
python3 scripts/research_market_states.py \
  --universe config/etf_universe.example.json \
  --start-date 20220101 \
  --end-date 20261231 \
  --output-dir tmp/market_regime
```

这个脚本本身非常薄，主要只做三件事：

1. 解析命令行参数
2. 调用 `research.pipeline.run_research()`
3. 打印输出文件路径

也就是说，真正的主流程并不写在 `scripts/` 目录，而写在 `research/pipeline.py`。

### 2. 主流程函数

整个研究流程由 `research.pipeline.run_research()` 负责组织。它的处理顺序是：

1. 读取 ETF universe
2. 提取所有 ETF symbol
3. 找出市场代理 ETF，并选定 benchmark
4. 批量加载所有 ETF 历史数据
5. 生成特征表
6. 生成每日 leaderboard
7. 生成每日市场状态表
8. 生成 summary
9. 把结果写入输出目录

最终输出：

- `daily_state.csv`
- `leaderboard.csv`
- `summary.json`

可以把 `run_research()` 理解为整个主策略的“总编排器”。

---

## 三、模块结构与职责

当前研究主策略主要由以下几个文件组成：

### 1. `research/etf_universe.py`

负责读取 ETF universe 配置文件，并将 JSON 转为结构化对象 `EtfUniverseEntry`。

每个 ETF 条目包含：

- `symbol`
- `name`
- `tags`
- `is_market_proxy`
- `is_theme_proxy`

这一步的作用是明确：

- 研究范围是什么
- 哪个标的是市场基准
- 哪些标的是主题候选

### 2. `research/data_loader.py`

负责批量拉取 ETF 历史数据。当前实现仍依赖根目录 `data.fallback_source.FallbackDataSource`。

它的职责是：

- 接收 ETF symbol 列表
- 按起止日期循环拉数
- 默认使用项目下的 `tmp/fallback_cache` 作为研究缓存目录
- 返回 `{symbol: DataFrame}` 的字典

这一步不做策略判断，只负责把标准化历史数据准备好。

### 3. `research/settings.py`

负责提供研究层自己的配置。

目前主要包括两部分：

- `DATA_SOURCE_PRIORITY`
- `MARKET_REGIME_PARAMS`

其中 `MARKET_REGIME_PARAMS` 决定了：

- 相对强弱窗口
- 动量窗口
- 均线窗口
- 量能窗口
- leaderboard 权重
- 市场阶段权重
- forward windows

### 4. `research/market_regime.py`

这是当前研究主策略最核心的文件，负责真正的研究逻辑。

其中主要函数有：

- `build_feature_table()`
- `build_leaderboard()`
- `build_daily_state()`
- `build_summary()`

它们分别对应：

- 特征工程
- 横截面排名
- 市场阶段识别
- 结果汇总

### 5. `research/pipeline.py`

负责把上面这些步骤串成一条可执行的研究链路。

---

## 四、输入数据与预期格式

### 1. ETF universe 输入

输入通常是一个 JSON 文件，例如：

```json
{
  "etfs": [
    {
      "symbol": "510300",
      "name": "沪深300ETF",
      "tags": ["宽基"],
      "is_market_proxy": true,
      "is_theme_proxy": false
    },
    {
      "symbol": "512480",
      "name": "半导体ETF",
      "tags": ["科技"],
      "is_market_proxy": false,
      "is_theme_proxy": true
    }
  ]
}
```

程序会从这里读取研究对象列表，并自动挑选第一个 `is_market_proxy=true` 的 ETF 作为 benchmark。

### 2. 行情数据格式

`research/data_loader.py` 通过 `FallbackDataSource` 返回每个 symbol 的 DataFrame。当前研究逻辑预期每个 DataFrame 至少具备以下列：

- `open`
- `high`
- `low`
- `close`
- `volume`

索引应为交易日期，并能按时间排序。

如果数据层无法提供这些字段，后续特征计算会失败。

---

## 五、研究参数说明

当前研究参数位于 `research/settings.py`。

### 1. 相对强弱窗口

```python
'relative_strength_windows': [20, 40, 60]
```

表示会分别计算 ETF 相对 benchmark 的：

- 20 日超额收益
- 40 日超额收益
- 60 日超额收益

然后取平均，形成 `relative_strength_score`。

### 2. 动量窗口

```python
'momentum_windows': [5, 10, 20]
```

表示会计算 ETF 自身：

- 5 日收益
- 10 日收益
- 20 日收益

再取平均形成 `momentum_score`。

### 3. 趋势均线参数

```python
'short_ma': 20,
'long_ma': 40,
```

它们用于判断：

- 当前收盘价是否站上短均线
- 短均线是否强于长均线

### 4. 成交量窗口

```python
'short_volume_window': 5,
'long_volume_window': 20,
```

用于计算量能活跃度，也就是当前的 `volume_price_score`。

### 5. leaderboard 权重

```python
'weights': {
    'relative_strength_score': 0.30,
    'momentum_score': 0.25,
    'volume_price_score': 0.25,
    'trend_support_score': 0.10,
    'stability_score': 0.10,
}
```

这表示当前版本在“主线 ETF 识别”上，最看重：

1. 相对强弱
2. 动量
3. 量能确认

趋势支撑和稳定性目前权重相对较低。

### 6. 市场阶段权重

```python
'market_weights': {
    'trend': 0.25,
    'breadth': 0.25,
    'volume_confirmation': 0.25,
    'cooldown_risk': 0.25,
}
```

这表示市场阶段打分目前是四等权设计，即：

- 趋势
- 广度
- 量能确认
- 风险冷却

这四类信号当前被同等看待。

---

## 六、特征工程：`build_feature_table()`

这是当前研究策略的第一层核心逻辑。

输入：

- `frames`: `dict[str, pd.DataFrame]`
- `benchmark_symbol`: 基准 ETF
- `params`: 研究参数

输出：

- 一张按 `date + symbol` 展开的特征表

### 1. benchmark 先计算相对收益基线

程序会先对 benchmark 的 `close` 计算多个窗口收益，用于后面计算每个 ETF 的超额收益。

### 2. 每个 ETF 单独计算滚动特征

对每个 ETF，会先生成这些中间列：

- `ma_short`
- `ma_long`
- `vol_short`
- `vol_long`

然后再逐日生成特征。

### 3. 当前主要特征

#### `relative_strength_score`

等于多个相对收益窗口的平均值。

含义：

- 该 ETF 是否持续跑赢 benchmark

#### `momentum_score`

等于多个动量窗口收益的平均值。

含义：

- 该 ETF 当前自身是否具备惯性和加速特征

#### `volume_price_score`

当前实现等于：

- `vol_short / vol_long`

含义：

- 最近量能是否比中期量能更强

注意：虽然名字里有 `price`，但当前实现更偏“量能确认”，暂时没有纳入价格形态附加条件。

#### `trend_support_score`

当前实现是两个布尔条件相加：

- `close > ma_short`
- `ma_short > ma_long`

取值大致是：

- 0：趋势弱
- 1：部分转强
- 2：趋势更健康

#### `stability_score`

当前固定为 `0.0`。

说明：

- 这个指标已经预留，但还未实现
- 未来可以用于衡量主线持续性、波动平滑度或 leader 连续性

### 4. 输出表的结构

最终特征表大体包含：

- `date`
- `symbol`
- `rs_20 / rs_40 / rs_60`
- `mom_5 / mom_10 / mom_20`
- `relative_strength_score`
- `momentum_score`
- `volume_price_score`
- `trend_support_score`
- `stability_score`

这张表是整个研究主策略的基础。

---

## 七、横截面排名：`build_leaderboard()`

这是当前研究策略的第二层核心逻辑。

输入：

- `feature_table`
- `params`

输出：

- 每个交易日的 ETF 排名表

### 1. 同日分组排名

程序会对每个交易日的所有 ETF，分别对以下列做组内百分位排序：

- `relative_strength_score`
- `momentum_score`
- `volume_price_score`
- `trend_support_score`
- `stability_score`

这一步的目的是让不同维度的特征能够在同一尺度上做组合。

### 2. 计算综合分数

然后程序会按权重加总，得到：

- `composite_score`

这个分数越高，表示该 ETF 在当前交易日越像主线。

### 3. 输出字段

当前 leaderboard 中最重要的列包括：

- `date`
- `symbol`
- 各分项得分
- `composite_score`
- `rank`
- `is_leader_candidate`

其中：

- `rank=1` 表示当天最强主线候选
- `is_leader_candidate=True` 表示进入前 3 名

### 4. 策略含义

这一层的本质不是“绝对判断强弱”，而是：

- 在今天所有 ETF 中
- 谁更像今天的市场主线
- 龙头是否突出
- 主线结构是否清晰

---

## 八、市场阶段识别：`build_daily_state()`

这是当前研究策略第三层、也是最像“策略核心”的部分。

输入：

- `frames`
- `leaderboard`
- `benchmark_symbol`
- `params`

输出：

- 日度市场状态表

### 1. benchmark 自身的环境特征

程序会先对 benchmark 计算：

- `ma_short`
- `ma_long`
- `ret_10`
- `ret_20`
- `dd_10`

其中 `dd_10` 表示近 10 日相对高点的回撤。

### 2. 每天从 leaderboard 中抽取前 3 名

对于每个日期，程序会取出当天 `rank` 最靠前的 3 个 ETF，作为：

- `leader_etf_top1`
- `leader_etf_top2`
- `leader_etf_top3`

### 3. 计算 daily state 的核心分量

#### `market_trend_score`

由 benchmark 的趋势关系构成：

- `close > ma_short`
- `ma_short > ma_long`

它反映市场代理当前是否仍处于健康趋势中。

#### `market_breadth_score`

观察当天 universe 中，有多少 ETF 趋势支撑较好。

当前写法使用：

- `(group['trend_support_score'] > 0.5).mean()`

它反映的是：

- 强势结构是否只集中在少数 ETF，还是具有广度

#### `volume_confirmation_score`

观察当天 universe 中，有多少 ETF 的量能分数较强。

它反映的是：

- 当前强势是否得到了成交量确认

#### `cooldown_risk_score`

由 benchmark 的近 10 日回撤计算而来。

它反映的是：

- 当前环境是否已经进入明显冷却或退潮状态

#### `leader_gap_score`

等于第一名和第二名 `composite_score` 的差值。

它反映的是：

- 龙头是否明显领先
- 当前主线是否清晰

#### `leader_stability_score`

当前实现为：

- `top['symbol'].nunique() <= 3`

由于当前只取前 3 名，这个写法区分度很弱，后续应该继续改进。

### 4. 计算市场阶段总分

程序用以下四项做加权：

- 趋势
- 广度
- 量能确认
- 风险冷却

得到：

- `market_stage_score`

### 5. 阶段分类规则

当前规则是：

- `market_stage_score >= 0.75` 且 `cooldown_risk < 0.08` -> `主升`
- `market_stage_score >= 0.60` 且 `cooldown_risk < 0.12` -> `启动`
- `cooldown_risk >= 0.15` -> `退潮`
- 其他情况 -> `混沌`

这个规则表达的是：

- 强趋势 + 低风险 = 主升
- 有一定趋势和确认，但还没到完全共振 = 启动
- 回撤过大 = 退潮
- 其余不清晰状态 = 混沌

---

## 九、开仓 gating：`can_open_new_position`

这是当前研究策略最重要的最终信号之一。

当前逻辑：

```python
can_open = stage in {'启动', '主升'} and leader_gap > 0.02
```

也就是说，只有在以下两个条件同时成立时，程序才认为可以开新仓：

1. 当前市场阶段属于 `启动` 或 `主升`
2. 龙头 ETF 和第二名 ETF 之间差距足够明显

这一条体现了你当前主策略的核心理念：

- 光有强 ETF 不够
- 光有环境偏强也不够
- 必须同时满足“环境适合进攻”和“主线足够清晰”

所以 `can_open_new_position` 不是某个 ETF 的买点，而是一个更上游的许可信号。

---

## 十、结果输出：你会拿到什么

`run_research()` 最终会把结果写到指定目录下。

### 1. `leaderboard.csv`

主要用于回答：

- 每天谁更强
- ETF 排名如何变化
- 主线是否发生轮动

常见关键字段：

- `date`
- `symbol`
- `composite_score`
- `rank`
- `is_leader_candidate`

### 2. `daily_state.csv`

主要用于回答：

- 今天市场阶段是什么
- 龙头 ETF 是谁
- 是否允许开仓

常见关键字段：

- `date`
- `market_stage`
- `market_stage_score`
- `leader_etf_top1`
- `leader_gap_score`
- `can_open_new_position`
- `open_position_reason`

### 3. `summary.json`

当前版本主要是基础统计，包括：

- 各市场阶段出现次数
- 开仓信号出现次数
- 龙头切换次数

当前它还是“统计摘要”，还不是完整的策略验证模块。

---

## 十一、如何理解这套策略的实际用途

当前 research 主策略适合作为下游执行系统的输入，而不是直接拿来下单。

举例来说，下游模块可以这样用：

1. 读取 `daily_state.csv`
2. 如果 `can_open_new_position=False`，则当天不做新开仓
3. 如果 `can_open_new_position=True`，再去读取 `leaderboard.csv`
4. 选择 `leader_etf_top1` 或前几名候选做进一步筛选
5. 再结合自己的交易执行规则决定：
   - 买哪个标的
   - 什么时候买
   - 买多少仓位
   - 什么条件离场

所以当前项目的结构更像：

- `research/` 负责上游判断
- `legacy/` 或未来的新执行层负责下游落地

---

## 十二、与 legacy 执行策略的关系

旧的 Backtrader 趋势策略依然保留，但它现在只是：

- 历史示例
- 执行参考
- 兼容保留代码

它和当前 research 主策略之间，不是“谁替代谁”的关系，而是：

- `research/` 负责 **告诉你什么时候值得做**
- `legacy/` 负责展示 **如果要做，过去是怎么执行买卖的**

也就是说，当前仓库已经从“单一交易策略项目”转向了“研究驱动的策略工程”。

---

## 十三、当前版本的局限与已知待扩展点

为了让读者对程序有完整认识，也需要明确当前实现还不完善的地方。

### 1. `stability_score` 还没有真正实现

当前固定为 `0.0`，说明稳定性因子只是预留位，后续还可以扩展。

### 2. `leader_stability_score` 区分度较弱

当前写法的辨识能力不强，更适合作为后续重做对象。

### 3. `volume_price_score` 当前更偏量能，不是完整量价模型

如果后续要增强，可以加入：

- 价格突破确认
- 波动结构
- 量价背离过滤

### 4. `build_summary()` 还只是统计汇总

当前尚未系统验证：

- 不同阶段下的 forward return
- `can_open_new_position` 的前瞻收益差异
- 主线切换与持续性质量

因此，当前 summary 更像研究输出摘要，而不是完整验证报告。

### 5. 当前只取第一个 `is_market_proxy=true` 作为 benchmark

这说明目前本质上还是单 benchmark 体系，不是多基准融合体系。

---

## 十四、建议的阅读顺序

如果你想快速从代码角度理解程序，我建议按以下顺序读：

1. `scripts/research_market_states.py`
   - 先看程序怎么启动
2. `research/pipeline.py`
   - 看整体主流程怎么串
3. `research/settings.py`
   - 看参数如何定义
4. `research/etf_universe.py`
   - 看研究对象如何定义
5. `research/market_regime.py`
   - 看特征、排名、状态、汇总如何计算
6. `research/data_loader.py`
   - 看数据如何批量接入

按照这个顺序读，最容易把“业务逻辑”和“代码结构”同时看清楚。

---

## 十五、一句话总结

当前版本项目的主策略，可以概括为：

**基于 ETF universe 的横截面强弱、动量、量能和趋势结构，识别市场阶段与主线 ETF，再输出是否允许开新仓的上游决策信号。**

如果把它翻译成更贴近程序运行的话，就是：

**先批量读 ETF 数据，再做日度打分和排名，再判断环境强弱，最后把“今天能不能做、主线是谁”作为研究结果输出出来。**
