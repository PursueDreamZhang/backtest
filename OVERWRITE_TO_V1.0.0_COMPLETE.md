这是一个“完整重构覆盖包”。

用法：
1. 切到你的仓库根目录
2. checkout 到 v1.0.0
3. 解压本 ZIP，覆盖同名文件
4. 运行研究入口验证
5. 直接 git add / git commit

推荐验证命令：

python3 scripts/research_market_states.py --universe config/etf_universe.example.json --start-date 20220101 --end-date 20261231 --output-dir tmp/market_regime

这次覆盖包做了两件事：

1. 让 research 成为主工程
2. 把旧 backtrader demo 逻辑复制到 legacy/ 下，同时保留根目录兼容入口

这个 ZIP 不依赖删除旧文件，所以解压覆盖后可以直接提交。
