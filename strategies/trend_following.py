"""趋势跟踪策略（弹簧体系增强版）。"""

import backtrader as bt


class TrendFollowingStrategy(bt.Strategy):
    """
    趋势跟踪策略（2026-04-03 弹簧增强版）

    买入条件：
    前置条件（筛选阶段）：
    1. 30天内涨幅超过 50% — 确认强势股
    2. 涨到顶点后开始回落 — 等待回调
    3. 靠近支撑位（20/40均线、箱体下沿）— 支撑位附近
    4. 调整期缩量 — 卖盘衰竭

    触发条件（买入信号）：
    5. 盘中相对昨收涨幅 >= 5% — 触发即买（不等待收盘）

    卖出条件：
    1. 跌破结构止损（趋势证伪点）或兜底止损 10%
    2. 无浮盈时，买入后2个交易日利润 < 3%
    3. 有浮盈时，跌破短均线/单日异常下跌
    """

    params = (
        # 买入参数
        ('surge_period', 30),        # 涨幅计算周期
        ('surge_threshold', 0.50),   # 涨幅阈值 50%
        ('ma_period', 40),           # 主趋势均线周期
        ('ma_short_period', 20),     # 次级支撑均线
        ('ma_exit_period', 10),      # 盈利单保护均线
        ('support_lookback', 20),    # 箱体低点回看
        ('support_range', 0.05),     # 支撑位附近范围 ±5%
        ('breakout_pct', 0.05),      # 突破涨幅 5%（修正：从3%改为5%）
        ('volume_shrink_ratio', 0.80),  # 缩量阈值：5日均量 <= 20日均量*0.8

        # 卖出参数
        ('stop_loss', 0.10),         # 兜底止损 10%
        ('profit_threshold', 0.03),  # 利润阈值 3%
        ('hold_days', 2),            # 持有天数检查
        ('drop_threshold', 0.05),    # 单日跌幅 5%

        # 仓位管理
        ('risk_per_trade', 0.02),    # 单笔最大可承受亏损占净值 2%
        ('position_pct_max', 0.15),  # 单票最大仓位 15%

        ('printlog', True),
    )

    def __init__(self):
        # 技术指标
        self.ma40 = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.ma20 = bt.indicators.SMA(self.data.close, period=self.p.ma_short_period)
        self.ma10 = bt.indicators.SMA(self.data.close, period=self.p.ma_exit_period)
        self.box_low = bt.indicators.MinN(self.data.low, period=self.p.support_lookback)
        self.vol_ma5 = bt.indicators.SMA(self.data.volume, period=5)
        self.vol_ma20 = bt.indicators.SMA(self.data.volume, period=20)

        # 30日涨幅（期间最高价相对于期间最低价的涨幅）
        self.high_30 = bt.indicators.MaxN(self.data.high, period=self.p.surge_period)
        self.low_30 = bt.indicators.MinN(self.data.low, period=self.p.surge_period)
        self.surge_30 = (self.high_30 - self.low_30) / self.low_30

        # 30日内最高点（用于判断是否从顶点回落）
        self.peak_30 = bt.indicators.MaxN(self.data.high, period=self.p.surge_period)

        # 状态追踪
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.buy_day = None  # 买入日期
        self.days_held = 0   # 持有天数
        self.structure_stop = None

        # 强势股标记（曾经出现过30日涨幅≥50%）
        self.had_surge = False
        self.surge_peak = 0  # 强势期间的最高点

    def log(self, txt, dt=None):
        """日志输出"""
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {txt}')

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.buy_day = len(self.data)
                self.days_held = 0
                # 用买入当日已知的支撑信息构建结构止损，作为趋势证伪点。
                support_floor = min(float(self.ma40[0]), float(self.box_low[0]), order.executed.price * 0.98)
                self.structure_stop = support_floor
                self.log(f'买入执行: 价格={order.executed.price:.2f}, '
                        f'成本={order.executed.value:.2f}, '
                        f'手续费={order.executed.comm:.2f}, '
                        f'结构止损={self.structure_stop:.2f}')
            else:
                self.log(f'卖出执行: 价格={order.executed.price:.2f}, '
                        f'成本={order.executed.value:.2f}, '
                        f'手续费={order.executed.comm:.2f}')
                self.structure_stop = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')

        self.order = None

    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return

        self.log(f'交易盈亏: 毛利={trade.pnl:.2f}, 净利={trade.pnlcomm:.2f}')

    def next(self):
        """策略主逻辑"""
        # 如果有未完成订单，不操作
        if self.order:
            return

        # 数据不足时跳过
        min_bars = max(self.p.surge_period, self.p.ma_period, self.p.support_lookback, 20)
        if len(self.data) < min_bars:
            return

        # 当前持仓
        current_position = self.position.size

        # === 买入逻辑 ===
        if not current_position:
            # 阶段1：检测是否出现过30日涨幅≥50%（标记为强势股）
            if self.surge_30[0] >= self.p.surge_threshold:
                self.had_surge = True
                self.surge_peak = self.peak_30[0]  # 记录强势期间的最高点

            # 阶段2：从强势高点回落
            if self.had_surge and self.surge_peak > 0:
                distance_from_peak = (self.surge_peak - self.data.close[0]) / self.surge_peak
                cond_pulled_back = distance_from_peak > 0.05  # 至少回落5%
            else:
                distance_from_peak = 0
                cond_pulled_back = False

            # 阶段3：靠近多支撑位（MA20/MA40/箱体下沿）。
            price = float(self.data.close[0])
            support_levels = [float(self.ma20[0]), float(self.ma40[0]), float(self.box_low[0])]
            support_distances = [abs(price - level) / level for level in support_levels if level > 0]
            min_support_distance = min(support_distances) if support_distances else 999
            cond_near_support = min_support_distance <= self.p.support_range

            # 阶段4：调整期缩量（5日均量显著低于20日均量）
            cond_volume_shrink = float(self.vol_ma5[0]) <= float(self.vol_ma20[0]) * self.p.volume_shrink_ratio

            # 阶段5：盘中突破触发（不等待收盘确认）
            intraday_change = (self.data.high[0] - self.data.close[-1]) / self.data.close[-1]
            cond_breakout = intraday_change >= self.p.breakout_pct

            # 调试输出（可选，每月1日输出）
            # if self.data.datetime.date(0).day == 1:
            #     self.log(f'条件检查: 强势={self.had_surge}(峰值{self.surge_peak:.1f}), '
            #             f'回落={distance_from_peak*100:.1f}%({cond_pulled_back}), '
            #             f'均线距离={ma_distance*100:.1f}%({cond_near_ma}), '
            #             f'盘中涨幅={intraday_change*100:.1f}%({cond_breakout})')

            # 所有买入条件（分阶段判断）
            if self.had_surge and cond_pulled_back and cond_near_support and cond_volume_shrink and cond_breakout:
                # 结构止损 + 以损定量仓位
                entry_price = price
                entry_stop = min(float(self.ma40[0]), float(self.box_low[0]), entry_price * 0.98)
                risk_per_share = max(entry_price - entry_stop, entry_price * 0.01)

                equity = self.broker.getvalue()
                cash = self.broker.getcash()
                size_by_risk = int((equity * self.p.risk_per_trade) / risk_per_share)
                size_by_cap = int((cash * self.p.position_pct_max) / entry_price)
                size = min(size_by_risk, size_by_cap)

                if size > 0:
                    self.log(f'买入信号: 30日涨幅曾达{self.surge_30[0]*100:.1f}%, '
                            f'距高点回落={distance_from_peak*100:.1f}%, '
                            f'支撑距离={min_support_distance*100:.1f}%, '
                            f'缩量比={float(self.vol_ma5[0]) / float(self.vol_ma20[0]):.2f}, '
                            f'盘中涨幅={intraday_change*100:.1f}%, '
                            f'仓位股数={size}')
                    self.order = self.buy(size=size)
                    self.had_surge = False  # 买入后重置强势标记
                    self.surge_peak = 0

        # === 卖出逻辑 ===
        else:
            # 更新持有天数
            self.days_held += 1

            # 计算当前盈亏
            profit_pct = (self.data.close[0] - self.buy_price) / self.buy_price

            # 条件1：结构止损（趋势证伪点）/兜底止损
            if self.structure_stop is not None and self.data.close[0] <= self.structure_stop:
                self.log(f'结构止损卖出: 当前={self.data.close[0]:.2f}, 止损位={self.structure_stop:.2f}')
                self.order = self.sell(size=current_position)
                return

            if profit_pct <= -self.p.stop_loss:
                self.log(f'止损卖出: 盈亏={profit_pct*100:.1f}%')
                self.order = self.sell(size=current_position)
                return

            # 条件2：持有到期后利润不达标就离场
            if self.days_held >= self.p.hold_days and profit_pct < self.p.profit_threshold:
                self.log(f'利润不达标卖出: 持有{self.days_held}天, 盈亏={profit_pct*100:.1f}%')
                self.order = self.sell(size=current_position)
                return

            # 条件3：有浮盈时让利润奔跑，但趋势钝化即离场
            if profit_pct > 0 and self.data.close[0] < self.ma10[0]:
                self.log(f'趋势钝化卖出: 收盘跌破MA{self.p.ma_exit_period}, 盈亏={profit_pct*100:.1f}%')
                self.order = self.sell(size=current_position)
                return

            # 条件4：异常反向波动
            daily_drop = (self.data.close[-1] - self.data.close[0]) / self.data.close[-1]
            if daily_drop >= self.p.drop_threshold:
                self.log(f'单日大跌卖出: 跌幅={daily_drop*100:.1f}%')
                self.order = self.sell(size=current_position)
                return

    def stop(self):
        """策略结束"""
        self.log(f'策略结束，最终资产: {self.broker.getvalue():.2f}')
