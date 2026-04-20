"""
自定义策略模板
在此文件中实现你自己的策略
"""

import backtrader as bt


class CustomStrategy(bt.Strategy):
    """
    自定义策略模板
    
    实现你自己的策略逻辑：
    1. 在 __init__ 中定义指标
    2. 在 next 中实现买卖逻辑
    """
    
    params = (
        ('param1', 20),  # 自定义参数
        ('printlog', True),
    )
    
    def __init__(self):
        # TODO: 定义你的指标
        # 示例：RSI
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.param1)
        
        # 示例：布林带
        self.boll = bt.indicators.BollingerBands(self.data.close, period=20)
        
        # 订单状态
        self.order = None
    
    def log(self, txt, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入: 价格={order.executed.price:.2f}')
            else:
                self.log(f'卖出: 价格={order.executed.price:.2f}')
        
        self.order = None
    
    def next(self):
        # 如果有订单在处理中，不操作
        if self.order:
            return
        
        # TODO: 实现你的策略逻辑
        # 示例：RSI 策略
        if not self.position:
            # RSI 超卖区买入
            if self.rsi < 30:
                self.order = self.buy()
        else:
            # RSI 超买区卖出
            if self.rsi > 70:
                self.order = self.sell()
