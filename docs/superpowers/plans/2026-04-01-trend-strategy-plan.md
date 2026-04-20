# 趋势跟踪策略实现计划

**目标：** 实现完整的趋势跟踪回测策略，捕捉强势股回调后的趋势延续

**架构：** 基于 Backtrader 框架，自定义 Strategy 类实现买卖逻辑，使用 yfinance 获取 A 股数据

**技术栈：** Python 3.13, Backtrader 1.9, yfinance 1.2, pandas

---

## 文件结构

```
/Users/zhangchunfu/Nutstore Files/code/backtest/
├── trend_strategy.py          # 修改：主策略实现
├── indicators.py              # 新建：自定义指标
└── tests/
    └── test_strategy.py       # 新建：策略单元测试
```

---

## 任务 1：创建自定义指标模块

**文件：**
- 创建：`/Users/zhangchunfu/Nutstore Files/code/backtest/indicators.py`

- [ ] **步骤 1：创建指标文件，实现 30日涨幅指标**

```python
"""
自定义技术指标
"""
import backtrader as bt


class SurgeIndicator(bt.Indicator):
    """
    30日涨幅指标
    计算：(30日最高价 - 30日最低价) / 30日最低价
    """
    lines = ('surge',)
    params = (('period', 30),)
    
    def __init__(self):
        self.lines.surge = (bt.Max(self.data.high, period=self.p.period) - 
                           bt.Min(self.data.low, period=self.p.period)) / \
                           bt.Min(self.data.low, period=self.p.period)
```

- [ ] **步骤 2：添加 5日均量指标**

```python
class VolumeMAIndicator(bt.Indicator):
    """
    成交量均线指标
    """
    lines = ('volume_ma',)
    params = (('period', 5),)
    
    def __init__(self):
        self.lines.volume_ma = bt.indicators.SMA(self.data.volume, period=self.p.period)
```

- [ ] **步骤 3：添加 5日高点指标**

```python
class HighBreakIndicator(bt.Indicator):
    """
    5日高点突破指标
    当日收盘价 > 过去5日最高价 时为 True
    """
    lines = ('breakout',)
    params = (('period', 5),)
    
    def __init__(self):
        self.lines.breakout = self.data.close > bt.Max(self.data.high(-1), period=self.p.period)
```

- [ ] **步骤 4：Commit**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
git add indicators.py
git commit -m "feat: add custom indicators (surge, volume_ma, high_break)"
```

---

## 任务 2：重写策略类 - 初始化部分

**文件：**
- 修改：`/Users/zhangchunfu/Nutstore Files/code/backtest/trend_strategy.py`

- [ ] **步骤 1：更新策略参数定义**

```python
class TrendFollowingStrategy(bt.Strategy):
    """
    趋势跟踪策略
    
    买入条件：
    1. 30日涨幅 >= 50%
    2. 股价回落到40日均线 ±5% 范围
    3. 突破确认：涨幅>=3% + 放量1.5倍 + 突破5日高点
    
    卖出条件：
    1. 亏损 >= 10% 止损
    2. 买入后2个交易日利润 < 3%
    3. 单日跌幅 >= 5%
    """
    
    params = (
        # 买入参数
        ('surge_period', 30),        # 涨幅计算周期
        ('surge_threshold', 0.50),   # 涨幅阈值 50%
        ('ma_period', 40),           # 均线周期
        ('ma_range', 0.05),          # 均线附近范围 ±5%
        ('breakout_pct', 0.03),      # 突破涨幅 3%
        ('volume_mult', 1.5),        # 放量倍数
        ('high_period', 5),          # 高点突破周期
        
        # 卖出参数
        ('stop_loss', 0.10),         # 止损 10%
        ('profit_threshold', 0.03),  # 利润阈值 3%
        ('hold_days', 2),            # 持有天数检查
        ('drop_threshold', 0.05),    # 单日跌幅 5%
        
        # 仓位管理
        ('position_pct', 0.20),      # 每次买入 20%
        
        ('printlog', True),
    )
```

- [ ] **步骤 2：实现 __init__ 方法**

```python
    def __init__(self):
        # 技术指标
        self.ma40 = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.volume_ma5 = bt.indicators.SMA(self.data.volume, period=self.p.high_period)
        
        # 30日涨幅
        self.high_30 = bt.Max(self.data.high, period=self.p.surge_period)
        self.low_30 = bt.Min(self.data.low, period=self.p.surge_period)
        self.surge_30 = (self.high_30 - self.low_30) / self.low_30
        
        # 5日高点（不含当日）
        self.high_5 = bt.Max(self.data.high(-1), period=self.p.high_period)
        
        # 状态追踪
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.buy_day = None  # 买入日期
        self.days_held = 0   # 持有天数
```

- [ ] **步骤 3：Commit**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
git add trend_strategy.py
git commit -m "feat: update strategy params and init method"
```

---

## 任务 3：实现买入逻辑

**文件：**
- 修改：`/Users/zhangchunfu/Nutstore Files/code/backtest/trend_strategy.py`

- [ ] **步骤 1：实现 next 方法 - 买入条件判断**

```python
    def next(self):
        # 如果有未完成订单，不操作
        if self.order:
            return
        
        # 当前持仓
        current_position = self.position.size
        
        # === 买入逻辑 ===
        if not current_position:
            # 条件1：30日涨幅 >= 50%
            cond_surge = self.surge_30[0] >= self.p.surge_threshold
            
            # 条件2：股价在40日均线 ±5% 范围内
            ma_distance = abs(self.data.close[0] - self.ma40[0]) / self.ma40[0]
            cond_ma = ma_distance <= self.p.ma_range
            
            # 条件3a：单日涨幅 >= 3%
            daily_change = (self.data.close[0] - self.data.close[-1]) / self.data.close[-1]
            cond_breakout_pct = daily_change >= self.p.breakout_pct
            
            # 条件3b：成交量 >= 5日均量的 1.5 倍
            cond_volume = self.data.volume[0] >= self.volume_ma5[0] * self.p.volume_mult
            
            # 条件3c：收盘价突破5日高点
            cond_high = self.data.close[0] > self.high_5[0]
            
            # 所有买入条件
            if cond_surge and cond_ma and cond_breakout_pct and cond_volume and cond_high:
                # 计算买入金额（20%仓位）
                cash_to_use = self.broker.getcash() * self.p.position_pct
                size = int(cash_to_use / self.data.close[0])
                
                if size > 0:
                    self.log(f'买入信号: 涨幅={self.surge_30[0]*100:.1f}%, '
                            f'均线距离={ma_distance*100:.1f}%, '
                            f'日涨幅={daily_change*100:.1f}%, '
                            f'放量={self.data.volume[0]/self.volume_ma5[0]:.1f}倍')
                    self.order = self.buy(size=size)
```

- [ ] **步骤 2：Commit**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
git add trend_strategy.py
git commit -m "feat: implement buy logic with all conditions"
```

---

## 任务 4：实现卖出逻辑

**文件：**
- 修改：`/Users/zhangchunfu/Nutstore Files/code/backtest/trend_strategy.py`

- [ ] **步骤 1：实现卖出条件判断**

```python
        # === 卖出逻辑 ===
        else:
            # 更新持有天数
            self.days_held += 1
            
            # 计算当前盈亏
            profit_pct = (self.data.close[0] - self.buy_price) / self.buy_price
            
            # 条件1：止损 10%
            if profit_pct <= -self.p.stop_loss:
                self.log(f'止损卖出: 盈亏={profit_pct*100:.1f}%')
                self.order = self.sell(size=current_position)
                return
            
            # 条件2：买入后2天利润不达3%
            if self.days_held >= self.p.hold_days and profit_pct < self.p.profit_threshold:
                self.log(f'利润不达标卖出: 持有{self.days_held}天, 盈亏={profit_pct*100:.1f}%')
                self.order = self.sell(size=current_position)
                return
            
            # 条件3：单日跌幅 >= 5%
            daily_drop = (self.data.close[-1] - self.data.close[0]) / self.data.close[-1]
            if daily_drop >= self.p.drop_threshold:
                self.log(f'单日大跌卖出: 跌幅={daily_drop*100:.1f}%')
                self.order = self.sell(size=current_position)
                return
```

- [ ] **步骤 2：Commit**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
git add trend_strategy.py
git commit -m "feat: implement sell logic with all conditions"
```

---

## 任务 5：实现订单回调

**文件：**
- 修改：`/Users/zhangchunfu/Nutstore Files/code/backtest/trend_strategy.py`

- [ ] **步骤 1：实现 notify_order 方法**

```python
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.buy_day = len(self.data)
                self.days_held = 0
                self.log(f'买入执行: 价格={order.executed.price:.2f}, '
                        f'成本={order.executed.value:.2f}, '
                        f'手续费={order.executed.comm:.2f}')
            else:
                self.log(f'卖出执行: 价格={order.executed.price:.2f}, '
                        f'成本={order.executed.value:.2f}, '
                        f'手续费={order.executed.comm:.2f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        
        self.order = None
```

- [ ] **步骤 2：实现 notify_trade 方法**

```python
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        
        self.log(f'交易盈亏: 毛利={trade.pnl:.2f}, 净利={trade.pnlcomm:.2f}')
```

- [ ] **步骤 3：实现 log 方法**

```python
    def log(self, txt, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {txt}')
```

- [ ] **步骤 4：实现 stop 方法**

```python
    def stop(self):
        self.log(f'策略结束，最终资产: {self.broker.getvalue():.2f}', dt=self.datas[0].datetime.date(0))
```

- [ ] **步骤 5：Commit**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
git add trend_strategy.py
git commit -m "feat: implement order callbacks and logging"
```

---

## 任务 6：更新数据获取函数

**文件：**
- 修改：`/Users/zhangchunfu/Nutstore Files/code/backtest/trend_strategy.py`

- [ ] **步骤 1：更新 get_stock_data 函数**

```python
def get_stock_data(symbol, start_date, end_date):
    """
    使用 yfinance 获取 A 股数据
    
    Args:
        symbol: 股票代码，如 '000001'
        start_date: 开始日期，如 '20200101'
        end_date: 结束日期，如 '20241231'
    
    Returns:
        pandas DataFrame
    """
    import yfinance as yf
    
    print(f'正在获取股票 {symbol} 数据...')
    
    # A股代码格式转换
    if symbol.startswith('6'):
        ticker = f"{symbol}.SS"  # 上海
    else:
        ticker = f"{symbol}.SZ"  # 深圳
    
    start_dt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    end_dt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
    
    df = yf.download(ticker, start=start_dt, end=end_dt, progress=False)
    
    # 重置索引
    df = df.reset_index()
    df = df.rename(columns={'Date': 'datetime', 'Open': 'open', 'High': 'high', 
                            'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    
    # 去除多级列名
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    print(f'获取完成，共 {len(df)} 条数据')
    return df
```

- [ ] **步骤 2：Commit**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
git add trend_strategy.py
git commit -m "feat: update data fetching function"
```

---

## 任务 7：更新主函数

**文件：**
- 修改：`/Users/zhangchunfu/Nutstore Files/code/backtest/trend_strategy.py`

- [ ] **步骤 1：更新 main 函数**

```python
def main():
    # 创建回测引擎
    cerebro = bt.Cerebro()
    
    # 添加策略
    cerebro.addstrategy(TrendFollowingStrategy, printlog=True)
    
    # 获取数据
    df = get_stock_data('300750', '20200101', '20241231')  # 宁德时代
    
    # 添加数据源
    data = bt.feeds.PandasData(
        dataname=df,
        fromdate=datetime.strptime('20200101', '%Y%m%d'),
        todate=datetime.strptime('20241231', '%Y%m%d')
    )
    cerebro.adddata(data)
    
    # 设置初始资金
    cerebro.broker.setcash(100000.0)
    
    # 设置佣金
    cerebro.broker.setcommission(commission=0.0003)
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 运行回测
    print('开始回测...')
    results = cerebro.run()
    strat = results[0]
    
    # 输出结果
    final_value = cerebro.broker.getvalue()
    print(f'\n{"="*60}')
    print(f'回测结果:')
    print(f'  最终资产: {final_value:,.2f}')
    print(f'  总盈亏: {final_value - 100000:,.2f} ({(final_value - 100000) / 100000 * 100:.2f}%)')
    
    sharpe = strat.analyzers.sharpe.get_analysis()
    if sharpe.get('sharperatio'):
        print(f'  夏普比率: {sharpe["sharperatio"]:.3f}')
    
    drawdown = strat.analyzers.drawdown.get_analysis()
    print(f'  最大回撤: {drawdown["max"]["drawdown"]:.2f}%')
    
    trades = strat.analyzers.trades.get_analysis()
    total = trades.get('total', {}).get('total', 0)
    won = trades.get('won', {}).get('total', 0)
    lost = trades.get('lost', {}).get('total', 0)
    if total > 0:
        print(f'  交易次数: {total}, 盈利: {won}, 亏损: {lost}, 胜率: {won/total*100:.1f}%')
    else:
        print(f'  交易次数: 0')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
```

- [ ] **步骤 2：Commit**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
git add trend_strategy.py
git commit -m "feat: update main function with analyzers"
```

---

## 任务 8：运行验证

- [ ] **步骤 1：运行回测验证**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
python3 trend_strategy.py
```

预期：有交易记录输出，无报错

- [ ] **步骤 2：检查输出**
- 确认交易次数 > 0
- 确认盈亏计算正确
- 确认夏普比率、最大回撤等指标输出

---

## 任务 9：更新 README

**文件：**
- 修改：`/Users/zhangchunfu/Nutstore Files/code/backtest/README.md`

- [ ] **步骤 1：更新策略说明**

```markdown
# 趋势跟踪策略回测框架

## 策略说明

### 买入条件
1. 30日涨幅 >= 50%
2. 股价回落到 40日均线 ±5% 范围
3. 突破确认（同时满足）：
   - 单日涨幅 >= 3%
   - 成交量 >= 5日均量的 1.5 倍
   - 收盘价突破 5日高点

### 卖出条件
1. 亏损 >= 10% 止损
2. 买入后 2 个交易日利润 < 3%
3. 单日跌幅 >= 5%

### 仓位管理
- 每次买入 20% 仓位

## 使用方法

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
python3 trend_strategy.py
```

## 参数优化

```bash
python3 optimize.py
```
```

- [ ] **步骤 2：Commit**

```bash
cd "/Users/zhangchunfu/Nutstore Files/code/backtest"
git add README.md
git commit -m "docs: update README with strategy details"
```

---

## 执行选项

计划写完保存到 `docs/superpowers/plans/2026-04-01-trend-strategy-plan.md`

**两种执行选项：**

**1. 子 Agent 驱动（推荐）** — 我为每个任务 dispatch 新的 subagent，任务间审查，快速迭代

**2. 顺序执行** — 在本 session 按批次执行任务，有审查检查点

选择哪种？
