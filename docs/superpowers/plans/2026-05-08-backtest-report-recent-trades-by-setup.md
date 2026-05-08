# Backtest Report Recent Trades By Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `watchlist_backtest` HTML report so the "最近交易" section is grouped by model (setup), each showing the latest 10 trades sorted by `entry_date` descending.

**Architecture:** Keep `report.html` self-contained and serverless. Generate HTML in `watchlist_backtest/reporting.py` by grouping the localized trades DataFrame by `setup`, sorting within each group by `entry_date`, and rendering one table per setup.

**Tech Stack:** Python, pandas, unittest, string-built HTML.

---

## File Map

- Modify: `/Users/zhangchunfu/my/mac/github/backtest/watchlist_backtest/reporting.py`
  - Change the HTML generation for the "最近交易" section.
- Create/Modify: `/Users/zhangchunfu/my/mac/github/backtest/tests/test_watchlist_backtest_reporting.py`
  - Unit tests for HTML grouping + latest-10-per-setup behavior.

---

### Task 1: Add A Focused HTML Generation Test

**Files:**
- Create: `/Users/zhangchunfu/my/mac/github/backtest/tests/test_watchlist_backtest_reporting.py`
- (Uses) `/Users/zhangchunfu/my/mac/github/backtest/watchlist_backtest/reporting.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path
import tempfile

import pandas as pd

from watchlist_backtest.reporting import write_backtest_reports


class BacktestReportingRecentTradesTests(unittest.TestCase):
    def _trades(self) -> pd.DataFrame:
        # Create >10 trades for setup A and a few trades for setup B with mixed entry dates.
        rows = []
        for i in range(12):
            rows.append(
                {
                    "symbol": f"00000{i}",
                    "name": f"Name{i}",
                    "direction": "D1",
                    "setup": "S-A",
                    "signal_date": "20260101",
                    "entry_date": f"202601{(i%9)+1:02d}",
                    "entry_price": 10.0,
                    "stop_loss_at_entry": 9.0,
                    "exit_date": "20260120",
                    "exit_price": 11.0,
                    "exit_reason": "max_hold_days",
                    "holding_days": 10,
                    "shares": 100,
                    "gross_pnl": 100.0,
                    "net_return": 0.01,
                }
            )
        for i in range(3):
            rows.append(
                {
                    "symbol": f"60000{i}",
                    "name": f"B{i}",
                    "direction": "D2",
                    "setup": "S-B",
                    "signal_date": "20260101",
                    "entry_date": f"202602{(i%9)+1:02d}",
                    "entry_price": 20.0,
                    "stop_loss_at_entry": 18.0,
                    "exit_date": "20260220",
                    "exit_price": 22.0,
                    "exit_reason": "max_hold_days",
                    "holding_days": 10,
                    "shares": 50,
                    "gross_pnl": 100.0,
                    "net_return": 0.02,
                }
            )
        return pd.DataFrame(rows)

    def test_report_groups_recent_trades_by_setup_and_limits_to_10(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            trades = self._trades()
            equity = pd.DataFrame([{"trade_date": "20260101", "cash": 1, "market_value": 0, "equity": 1, "positions": 0}])
            diary = pd.DataFrame(columns=["trade_date","symbol","name","direction","thesis","group","setup","score","latest_price","support","stop_loss","risk_to_stop_pct","action"])
            summary = {
                "initial_cash": 1.0,
                "final_equity": 1.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "trade_count": int(len(trades)),
                "signal_count": 0,
                "win_rate_pct": 0.0,
                "avg_win_pct": 0.0,
                "avg_loss_pct": 0.0,
                "avg_holding_days": 0.0,
                "by_setup": [
                    {"setup": "S-A", "trades": 12, "win_rate_pct": 0.0, "avg_return_pct": 0.0},
                    {"setup": "S-B", "trades": 3, "win_rate_pct": 0.0, "avg_return_pct": 0.0},
                ],
                "by_direction": [],
            }
            paths = write_backtest_reports(
                output_dir=str(out),
                trades=trades,
                equity_curve=equity,
                signal_diary=diary,
                summary=summary,
            )
            html = Path(paths["html"]).read_text(encoding="utf-8")

            # Each setup should have its own table/section.
            self.assertIn("最近交易（S-A）", html)
            self.assertIn("最近交易（S-B）", html)

            # S-A should be limited to 10 rows.
            sa_section = html.split("最近交易（S-A）", 1)[1].split("</table>", 1)[0]
            self.assertLessEqual(sa_section.count("<tr>"), 11)  # header row + up to 10 data rows

            # S-B has only 3 rows.
            sb_section = html.split("最近交易（S-B）", 1)[1].split("</table>", 1)[0]
            self.assertLessEqual(sb_section.count("<tr>"), 4)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
/Users/zhangchunfu/my/mac/github/backtest/.venv/bin/python -m unittest -v tests.test_watchlist_backtest_reporting.BacktestReportingRecentTradesTests
```

Expected: FAIL because the HTML still uses a single "最近交易" table and does not contain "最近交易（S-A）".

---

### Task 2: Implement Grouped Recent Trades Rendering

**Files:**
- Modify: `/Users/zhangchunfu/my/mac/github/backtest/watchlist_backtest/reporting.py`
- Test: `/Users/zhangchunfu/my/mac/github/backtest/tests/test_watchlist_backtest_reporting.py`

- [ ] **Step 1: Add a helper to build recent-trades HTML by setup**

Implement a small helper function near the HTML generation area:

```python
def _render_recent_trades_by_setup(localized_trades: pd.DataFrame, *, limit_per_setup: int = 10) -> str:
    if localized_trades.empty:
        return "<p>无交易记录。</p>"

    # Ensure deterministic ordering: setup name asc, then entry_date desc within setup.
    pieces: list[str] = []
    for setup, group in localized_trades.groupby("setup", sort=True):
        sorted_group = group.sort_values(
            by=["entry_date", "symbol", "exit_date"],
            ascending=[False, True, False],
            kind="mergesort",
        ).head(limit_per_setup)

        rows = "".join(
            f\"<tr><td>{row['symbol']}</td><td>{row['name']}</td><td>{row['direction']}</td><td>{row['setup']}</td>\"
            f\"<td>{row['entry_date']}</td><td>{row['exit_date']}</td><td>{row['exit_reason']}</td>\"
            f\"<td>{row['net_return'] * 100:.2f}%</td></tr>\"
            for _, row in sorted_group.iterrows()
        )

        pieces.append(
            f\"<h3 id='recent-{setup}'>最近交易（{setup}）</h3>\"
            f\"<table><thead><tr><th>代码</th><th>名称</th><th>方向</th><th>模型</th><th>买入日</th><th>卖出日</th><th>原因</th><th>收益</th></tr></thead><tbody>{rows}</tbody></table>\"
        )

    return \"\\n\".join(pieces)
```

Notes:

- `entry_date` is `YYYYMMDD`, lexical sort works as date sort.
- Use mergesort for stable ordering.

- [ ] **Step 2: Wire the helper into the main HTML template**

Replace the existing `trade_rows` / single table block with:

- `recent_trades_html = _render_recent_trades_by_setup(localized_trades, limit_per_setup=10)`
- In HTML body:
  - Keep `<h2>最近交易</h2>`
  - Insert `{recent_trades_html}` instead of the single table.

- [ ] **Step 3: Run the new unit test**

Run:

```bash
/Users/zhangchunfu/my/mac/github/backtest/.venv/bin/python -m unittest -v tests.test_watchlist_backtest_reporting.BacktestReportingRecentTradesTests
```

Expected: PASS.

- [ ] **Step 4: Run a quick regression smoke test (optional but recommended)**

Run:

```bash
/Users/zhangchunfu/my/mac/github/backtest/.venv/bin/python -m unittest -v tests.test_watchlist_backtest_engine
```

Expected: PASS (ensures report writing still works end-to-end).

- [ ] **Step 5: Commit**

```bash
git add /Users/zhangchunfu/my/mac/github/backtest/watchlist_backtest/reporting.py \
  /Users/zhangchunfu/my/mac/github/backtest/tests/test_watchlist_backtest_reporting.py
git commit -m "feat: group recent trades by setup in backtest report"
```

---

### Task 3: Regenerate The Existing HTML Output For Visual Verification

**Files:**
- Re-generate (by running the same backtest entrypoint you used before): output under
  - `/Users/zhangchunfu/my/mac/github/backtest/tmp/watchlist_backtest_20250101_20260506/report.html`

- [ ] **Step 1: Re-run the backtest script that produced this output**

Find the command used previously (shell history or docs) and re-run it with the same `--output-dir`.

If unknown, re-run with the existing artifacts as inputs is not supported; instead, rerun:

```bash
/Users/zhangchunfu/my/mac/github/backtest/.venv/bin/python scripts/backtest_watchlist_strategy.py \
  --config /Users/zhangchunfu/my/mac/github/backtest/config/watchlists.json \
  --start-date 20250101 \
  --end-date 20260506 \
  --output-dir /Users/zhangchunfu/my/mac/github/backtest/tmp/watchlist_backtest_20250101_20260506
```

Expected: `report.html` updated and now shows per-setup recent trade tables.

