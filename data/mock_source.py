"""
模拟数据源
生成符合策略条件的测试数据
"""

import numpy as np
import pandas as pd


class MockDataSource:
    """模拟数据源"""
    
    def get_data(self, days=500):
        """
        生成符合策略条件的模拟数据
        
        Args:
            days: 生成的天数，默认500天
        
        Returns:
            pandas DataFrame
        """
        print(f'生成模拟数据 {days} 天（含趋势行情）...')
        
        dates = pd.date_range(start='2022-01-01', periods=days, freq='D')
        
        np.random.seed(42)
        
        # 分阶段生成价格
        prices = []
        base = 100
        
        # 阶段1: 前100天震荡
        for i in range(100):
            prices.append(base + np.random.randn() * 2)
        
        # 阶段2: 30天暴涨60%（满足30日涨幅>50%）
        for i in range(30):
            pct = 0.02 + np.random.rand() * 0.02
            prices.append(prices[-1] * (1 + pct))
        
        peak = prices[-1]
        
        # 阶段3: 回落到均线附近（回落15-20%）
        ma_target = peak * 0.82
        for i in range(25):
            prices.append(prices[-1] * 0.992 + np.random.randn() * 0.5)
        
        # 阶段4: 均线附近震荡25天
        for i in range(25):
            prices.append(ma_target + np.random.randn() * 1.5)
        
        # 阶段5: 突破日（单日涨幅>=5%）
        prev_close = prices[-1]
        breakout_close = prev_close * 1.06
        prices.append(breakout_close)
        print(f'突破日: 前收{prev_close:.2f}, 当收{breakout_close:.2f}, 涨幅6%')
        
        # 阶段6: 后续走势
        remaining = days - len(prices)
        for i in range(remaining):
            change = np.random.randn() * 0.02
            prices.append(prices[-1] * (1 + change))
        
        prices = np.array(prices[:days])
        
        df = pd.DataFrame({
            'open': prices * (1 + np.random.randn(days) * 0.005),
            'high': prices * (1 + np.abs(np.random.randn(days)) * 0.015),
            'low': prices * (1 - np.abs(np.random.randn(days)) * 0.015),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, days)
        }, index=dates)
        
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        print(f'生成完成，共 {len(df)} 条数据')
        print(f'峰值价格: {peak:.2f}')
        
        return df
