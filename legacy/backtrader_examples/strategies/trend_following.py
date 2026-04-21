"""趋势跟踪策略（弹簧体系增强版）。"""

import backtrader as bt


class TrendFollowingStrategy(bt.Strategy):
    params = (
        ('surge_period', 30),
        ('surge_threshold', 0.50),
        ('ma_period', 40),
        ('ma_short_period', 20),
        ('ma_exit_period', 10),
        ('support_lookback', 20),
        ('support_range', 0.05),
        ('breakout_pct', 0.05),
        ('volume_shrink_ratio', 0.80),
        ('stop_loss', 0.10),
        ('profit_threshold', 0.03),
        ('hold_days', 2),
        ('drop_threshold', 0.05),
        ('risk_per_trade', 0.02),
        ('position_pct_max', 0.15),
        ('printlog', True),
    )

    def __init__(self):
        self.ma40 = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.ma20 = bt.indicators.SMA(self.data.close, period=self.p.ma_short_period)
        self.ma10 = bt.indicators.SMA(self.data.close, period=self.p.ma_exit_period)
        self.box_low = bt.indicators.MinN(self.data.low, period=self.p.support_lookback)
        self.vol_ma5 = bt.indicators.SMA(self.data.volume, period=5)
        self.vol_ma20 = bt.indicators.SMA(self.data.volume, period=20)
        self.high_30 = bt.indicators.MaxN(self.data.high, period=self.p.surge_period)
        self.low_30 = bt.indicators.MinN(self.data.low, period=self.p.surge_period)
        self.surge_30 = (self.high_30 - self.low_30) / self.low_30
        self.peak_30 = bt.indicators.MaxN(self.data.high, period=self.p.surge_period)

        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.buy_day = None
        self.days_held = 0
        self.structure_stop = None
        self.had_surge = False
        self.surge_peak = 0

    def log(self, txt, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.buy_day = len(self.data)
                self.days_held = 0
                support_floor = min(float(self.ma40[0]), float(self.box_low[0]), order.executed.price * 0.98)
                self.structure_stop = support_floor
                self.log(f'买入执行: 价格={order.executed.price:.2f}, 成本={order.executed.value:.2f}, 手续费={order.executed.comm:.2f}, 结构止损={self.structure_stop:.2f}')
            else:
                self.log(f'卖出执行: 价格={order.executed.price:.2f}, 成本={order.executed.value:.2f}, 手续费={order.executed.comm:.2f}')
                self.structure_stop = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'交易盈亏: 毛利={trade.pnl:.2f}, 净利={trade.pnlcomm:.2f}')

    def next(self):
        if self.order:
            return

        min_bars = max(self.p.surge_period, self.p.ma_period, self.p.support_lookback, 20)
        if len(self.data) < min_bars:
            return

        current_position = self.position.size

        if not current_position:
            if self.surge_30[0] >= self.p.surge_threshold:
                self.had_surge = True
                self.surge_peak = self.peak_30[0]

            if self.had_surge and self.surge_peak > 0:
                distance_from_peak = (self.surge_peak - self.data.close[0]) / self.surge_peak
                cond_pulled_back = distance_from_peak > 0.05
            else:
                distance_from_peak = 0
                cond_pulled_back = False

            price = float(self.data.close[0])
            support_levels = [float(self.ma20[0]), float(self.ma40[0]), float(self.box_low[0])]
            support_distances = [abs(price - level) / level for level in support_levels if level > 0]
            min_support_distance = min(support_distances) if support_distances else 999
            cond_near_support = min_support_distance <= self.p.support_range

            cond_volume_shrink = float(self.vol_ma5[0]) <= float(self.vol_ma20[0]) * self.p.volume_shrink_ratio
            intraday_change = (self.data.high[0] - self.data.close[-1]) / self.data.close[-1]
            cond_breakout = intraday_change >= self.p.breakout_pct

            if self.had_surge and cond_pulled_back and cond_near_support and cond_volume_shrink and cond_breakout:
                entry_price = price
                entry_stop = min(float(self.ma40[0]), float(self.box_low[0]), entry_price * 0.98)
                risk_per_share = max(entry_price - entry_stop, entry_price * 0.01)

                equity = self.broker.getvalue()
                cash = self.broker.getcash()
                size_by_risk = int((equity * self.p.risk_per_trade) / risk_per_share)
                size_by_cap = int((cash * self.p.position_pct_max) / entry_price)
                size = min(size_by_risk, size_by_cap)

                if size > 0:
                    self.log(f'买入信号: 30日涨幅曾达{self.surge_30[0]*100:.1f}%, 距高点回落={distance_from_peak*100:.1f}%, 支撑距离={min_support_distance*100:.1f}%, 缩量比={float(self.vol_ma5[0]) / float(self.vol_ma20[0]):.2f}, 盘中涨幅={intraday_change*100:.1f}%, 仓位股数={size}')
                    self.order = self.buy(size=size)
                    self.had_surge = False
                    self.surge_peak = 0

        else:
            self.days_held += 1
            profit_pct = (self.data.close[0] - self.buy_price) / self.buy_price

            if self.structure_stop is not None and self.data.close[0] <= self.structure_stop:
                self.log(f'结构止损卖出: 当前={self.data.close[0]:.2f}, 止损位={self.structure_stop:.2f}')
                self.order = self.sell(size=current_position)
                return

            if profit_pct <= -self.p.stop_loss:
                self.log(f'止损卖出: 盈亏={profit_pct*100:.1f}%')
                self.order = self.sell(size=current_position)
                return

            if self.days_held >= self.p.hold_days and profit_pct < self.p.profit_threshold:
                self.log(f'利润不达标卖出: 持有{self.days_held}天, 盈亏={profit_pct*100:.1f}%')
                self.order = self.sell(size=current_position)
                return

            if profit_pct > 0 and self.data.close[0] < self.ma10[0]:
                self.log(f'趋势钝化卖出: 收盘跌破MA{self.p.ma_exit_period}, 盈亏={profit_pct*100:.1f}%')
                self.order = self.sell(size=current_position)
                return

            daily_drop = (self.data.close[-1] - self.data.close[0]) / self.data.close[-1]
            if daily_drop >= self.p.drop_threshold:
                self.log(f'单日大跌卖出: 跌幅={daily_drop*100:.1f}%')
                self.order = self.sell(size=current_position)
                return

    def stop(self):
        self.log(f'策略结束，最终资产: {self.broker.getvalue():.2f}')
