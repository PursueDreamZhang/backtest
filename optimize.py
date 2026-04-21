"""兼容入口：旧参数优化逻辑已迁入 legacy/backtrader_examples。"""

from legacy.backtrader_examples.optimize import optimize_strategy

__all__ = ['optimize_strategy']

if __name__ == '__main__':
    optimize_strategy()
