"""兼容入口：旧回测逻辑已迁入 legacy/backtrader_examples。"""

from legacy.backtrader_examples.main import run_backtest

__all__ = ['run_backtest']

if __name__ == '__main__':
    run_backtest()
