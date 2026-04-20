# 2026-04-10 Daily Watchlist

## Goal

新增一个每日执行脚本，自动：

1. 读取最新 A 股股票池
2. 拉取最新日线数据并复用本地缓存
3. 读取本地持仓文件
4. 输出两组标的到 JSON：
   - `held_positions`
   - `watch_candidates`

## Candidate Rules

`watch_candidates` 必须同时满足：

1. 第一段强势条件：
   - 30 天内涨幅超过 50%
2. 第二段观察条件：
   - 从高点回落至少 5%
   - 靠近支撑位

## Files

- Create: `scripts/daily_watchlist.py`
- Create: `config/holdings.example.json`
- Create: `tests/test_daily_watchlist.py`

## Steps

1. 实现股票池和持仓文件读取
2. 实现单票最新行情拉取与缓存复用
3. 实现候选观察条件计算
4. 实现 JSON 输出
5. 为候选观察逻辑补单元测试
6. 运行测试
7. 实跑脚本验证输出文件生成
