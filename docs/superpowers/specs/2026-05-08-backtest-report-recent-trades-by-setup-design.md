# Backtest Report: Recent Trades By Setup

## Goal

Optimize the `watchlist_backtest` HTML report so the "最近交易" section is displayed *by model (setup)*, showing the **latest 10 trades per setup**.

The user confirmed "latest" is defined as **descending by entry date (`entry_date`)**.

## Non-Goals

- No changes to backtest logic, signal generation, or trading rules.
- No change to CSV/JSON output formats.
- No JS-heavy UI; keep it as a single self-contained HTML file.

## Current Behavior

`watchlist_backtest/reporting.py` renders "最近交易" using `localized_trades.head(30)`, which is:

- Not guaranteed to be "recent" unless the input trade list is pre-sorted.
- Not grouped by setup.

## Proposed Behavior

Replace the single "最近交易" table with a per-setup rendering:

- Group trades by `setup` (模型).
- For each setup:
  - Sort trades by `entry_date` descending (string YYYYMMDD, safe for lexical sort).
  - Take top 10 rows.
  - Render a table titled `最近交易（<setup>）` (or similar).

### Sorting Rule

Primary sort: `entry_date` descending.

Tie-breakers (stable display):

- `symbol` ascending
- `exit_date` descending (optional; used only to keep output stable)

## UX / Layout

- Keep the existing page structure (metrics grid, model stats, direction stats).
- Replace the single "最近交易" section with:
  - An optional quick index (anchors) listing setups for fast navigation (nice-to-have).
  - Multiple tables, one per setup.

## Acceptance Criteria

- For each model present in `trades.csv`, the HTML report contains a "最近交易" table for that model.
- Each table has at most 10 rows.
- Rows within a table are ordered by latest `entry_date` first.
- Existing outputs (`trades.csv`, `equity_curve.csv`, `signal_diary.csv`, `summary.json`) remain unchanged.

## Testing

- Add/adjust a unit test for `watchlist_backtest/reporting.py` HTML generation:
  - Given a small synthetic `trades` DataFrame with multiple setups and mixed entry dates,
  - Generated HTML contains separate sections per setup,
  - Each section includes only the latest 10 by entry date.

