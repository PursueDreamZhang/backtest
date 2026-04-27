from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .etf_universe import EtfUniverseEntry

STAGE_COLORS = {
    '主升': 'rgba(205, 92, 92, 0.13)',
    '启动': 'rgba(127, 176, 105, 0.14)',
    '混沌': 'rgba(214, 170, 71, 0.26)',
    '退潮': 'rgba(77, 92, 120, 0.28)',
}

STAGE_TEXT_COLORS = {
    '主升': '#9f3a38',
    '启动': '#47683c',
    '混沌': '#8a6616',
    '退潮': '#31415f',
}

STAGE_CHIP_BG_COLORS = {
    '主升': '#f1e4e2',
    '启动': '#e5eee1',
    '混沌': '#efe4c4',
    '退潮': '#dbe2eb',
}

MARKET_PROXY_COLORS = [
    '#c0392b',
    '#d35400',
    '#f39c12',
    '#16a085',
    '#27ae60',
    '#2980b9',
    '#8e44ad',
    '#2c3e50',
    '#7f8c8d',
    '#34495e',
]

THEME_PROXY_COLOR = '#bdc3c7'


def build_stage_bands(daily_state: pd.DataFrame) -> list[dict[str, object]]:
    work = daily_state[['date', 'market_stage']].copy()
    work['date'] = pd.to_datetime(work['date'])
    work = work.sort_values('date').reset_index(drop=True)
    if work.empty:
        return []

    bands: list[dict[str, object]] = []
    current_stage = str(work.iloc[0]['market_stage'])
    start_idx = 0

    for idx, row in enumerate(work.iloc[1:].itertuples(index=False), start=1):
        stage = str(row.market_stage)
        if stage == current_stage:
            continue

        bands.append(
            {
                'stage': current_stage,
                'start_idx': start_idx,
                'end_idx': idx - 1,
                'mid_idx': (start_idx + idx - 1) / 2.0,
                'color': STAGE_COLORS.get(current_stage, STAGE_COLORS['混沌']),
            }
        )
        current_stage = stage
        start_idx = idx

    bands.append(
        {
            'stage': current_stage,
            'start_idx': start_idx,
            'end_idx': len(work) - 1,
            'mid_idx': (start_idx + len(work) - 1) / 2.0,
            'color': STAGE_COLORS.get(current_stage, STAGE_COLORS['混沌']),
        }
    )
    return bands


def _normalize_close_series(frame: pd.DataFrame) -> pd.Series:
    work = frame[['close']].copy().sort_index()
    work = work[work['close'].notna()]
    if work.empty:
        return pd.Series(dtype=float)

    base_close = float(work.iloc[0]['close'])
    if base_close == 0:
        return pd.Series(dtype=float)
    return (work['close'] / base_close).round(6)


def build_dashboard_payload(
    universe: list[EtfUniverseEntry],
    frames: dict[str, pd.DataFrame],
    daily_state: pd.DataFrame,
    leaderboard: pd.DataFrame,
    title: str,
) -> dict[str, object]:
    daily_state_work = daily_state.copy()
    daily_state_work['date'] = pd.to_datetime(daily_state_work['date'])
    trading_dates = daily_state_work['date'].sort_values().dt.strftime('%Y-%m-%d').tolist()
    trading_index_by_date = {date: idx for idx, date in enumerate(trading_dates)}
    stage_by_date = {
        row.date.strftime('%Y-%m-%d'): str(row.market_stage)
        for row in daily_state_work[['date', 'market_stage']].itertuples(index=False)
    }
    latest_row = daily_state_work.sort_values('date').iloc[-1] if not daily_state_work.empty else None
    universe_map = {item.symbol: item for item in universe}
    leaderboard_work = leaderboard.copy()
    leaderboard_work['date'] = pd.to_datetime(leaderboard_work['date']).dt.strftime('%Y-%m-%d')
    metric_map = {
        (str(row.date), str(row.symbol)): {
            'daily_return_pct': float(getattr(row, 'daily_return_pct', 0.0)),
            'open_to_close_return': float(getattr(row, 'open_to_close_return', 0.0)),
            'high_to_close_gap': float(getattr(row, 'high_to_close_gap', 0.0)),
        }
        for row in leaderboard_work.itertuples(index=False)
    }
    latest_top5_symbols = [
        str(latest_row.get(f'leader_etf_top{i}') or '')
        for i in range(1, 6)
        if latest_row is not None and str(latest_row.get(f'leader_etf_top{i}') or '')
    ]
    latest_top5_rank_by_symbol = {symbol: idx + 1 for idx, symbol in enumerate(latest_top5_symbols)}
    latest_date = latest_row['date'].strftime('%Y-%m-%d') if latest_row is not None else ''
    latest_top5_details = []
    for symbol in latest_top5_symbols:
        item = universe_map.get(symbol)
        metrics = metric_map.get((latest_date, symbol), {})
        latest_top5_details.append(
            {
                'rank': latest_top5_rank_by_symbol[symbol],
                'symbol': symbol,
                'name': item.name if item else symbol,
                'tags': list(item.tags) if item else [],
                'daily_return_pct': metrics.get('daily_return_pct', 0.0),
                'open_to_close_return': metrics.get('open_to_close_return', 0.0),
                'high_to_close_gap': metrics.get('high_to_close_gap', 0.0),
            }
        )

    traces: list[dict[str, object]] = []
    market_color_index = 0

    for item in universe:
        if item.symbol not in frames:
            continue
        normalized = _normalize_close_series(frames[item.symbol])
        if normalized.empty:
            continue

        available = [
            (
                trading_index_by_date[date_str],
                date_str,
                float(value),
                metric_map.get((date_str, item.symbol), {}),
            )
            for date_str, value in zip(
                [index.strftime('%Y-%m-%d') for index in normalized.index],
                normalized.tolist(),
            )
            if date_str in trading_index_by_date
        ]
        if not available:
            continue

        color = (
            MARKET_PROXY_COLORS[market_color_index % len(MARKET_PROXY_COLORS)]
            if item.is_market_proxy
            else THEME_PROXY_COLOR
        )
        if item.is_market_proxy:
            market_color_index += 1

        rank_badge = latest_top5_rank_by_symbol.get(item.symbol)
        display_name = (
            f'[{rank_badge}] {item.symbol} {item.name}'
            if rank_badge is not None
            else f'{item.symbol} {item.name}'
        )

        traces.append(
            {
                'symbol': item.symbol,
                'name': f'{item.symbol} {item.name}',
                'display_name': display_name,
                'x': [entry[0] for entry in available],
                'dates': [entry[1] for entry in available],
                'stages': [stage_by_date[entry[1]] for entry in available],
                'y': [entry[2] for entry in available],
                'daily_return_pct': [entry[3].get('daily_return_pct', 0.0) for entry in available],
                'open_to_close_return': [entry[3].get('open_to_close_return', 0.0) for entry in available],
                'high_to_close_gap': [entry[3].get('high_to_close_gap', 0.0) for entry in available],
                'visible': item.symbol in latest_top5_rank_by_symbol,
                'category': 'market' if item.is_market_proxy else 'theme',
                'tags': list(item.tags),
                'color': color,
            }
        )

    return {
        'title': title,
        'latest_snapshot': {
            'date': latest_row['date'].strftime('%Y-%m-%d') if latest_row is not None else '',
            'market_stage': str(latest_row['market_stage']) if latest_row is not None else '',
            'leader_direction_summary': str(latest_row.get('leader_direction_summary') or '') if latest_row is not None else '',
            'top5_symbols': latest_top5_symbols,
            'top5_details': latest_top5_details,
        },
        'x_labels': trading_dates,
        'bands': build_stage_bands(daily_state),
        'traces': traces,
    }


def render_dashboard_html(payload: dict[str, object], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    payload_json = json.dumps(payload, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{payload['title']}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg: #f5f1e8;
      --card: #fffdf7;
      --ink: #17202a;
      --muted: #6b7280;
      --line: #e5dccb;
    }}
    body {{
      margin: 0;
      font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(207, 216, 220, 0.35), transparent 30%),
        linear-gradient(180deg, #f8f3ea 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    .page {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }}
    .header {{
      margin-bottom: 16px;
    }}
    .title {{
      font-size: 28px;
      font-weight: 700;
      margin: 0 0 8px;
    }}
    .subtitle {{
      color: var(--muted);
      margin: 0;
      line-height: 1.6;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 16px 0 20px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 13px;
    }}
    .chip-label {{
      font-weight: 600;
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
    }}
    .card {{
      background: rgba(255, 253, 247, 0.92);
      border: 1px solid rgba(229, 220, 203, 0.9);
      border-radius: 20px;
      padding: 16px;
      box-shadow: 0 12px 40px rgba(109, 76, 65, 0.08);
    }}
    .top5-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .top5-item {{
      border: 1px solid rgba(229, 220, 203, 0.9);
      border-radius: 16px;
      padding: 12px 14px;
      background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(248,243,234,0.88));
    }}
    .top5-rank {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: #17202a;
      color: #fffdf7;
      font-size: 12px;
      font-weight: 700;
      margin-right: 8px;
    }}
    .top5-name {{
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
    }}
    .top5-symbol {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }}
    .top5-metric {{
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.6;
    }}
    #chart {{
      width: 100%;
      height: 760px;
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="header">
      <h1 class="title">{payload['title']}</h1>
      <p class="subtitle">默认展示市场代表 ETF，行业 ETF 已加载到图例中，点击即可显示或隐藏。背景色表示每日市场阶段。</p>
      <p class="subtitle" id="latest-summary"></p>
    </div>
    <div class="legend">
      <span class="chip" style="background:{STAGE_CHIP_BG_COLORS['启动']}; border-color:{STAGE_TEXT_COLORS['启动']}33;">
        <span class="dot" style="background:{STAGE_TEXT_COLORS['启动']}"></span>
        <span class="chip-label" style="color:{STAGE_TEXT_COLORS['启动']};">启动</span>
      </span>
      <span class="chip" style="background:{STAGE_CHIP_BG_COLORS['主升']}; border-color:{STAGE_TEXT_COLORS['主升']}33;">
        <span class="dot" style="background:{STAGE_TEXT_COLORS['主升']}"></span>
        <span class="chip-label" style="color:{STAGE_TEXT_COLORS['主升']};">主升</span>
      </span>
      <span class="chip" style="background:{STAGE_CHIP_BG_COLORS['混沌']}; border-color:{STAGE_TEXT_COLORS['混沌']}33;">
        <span class="dot" style="background:{STAGE_TEXT_COLORS['混沌']}"></span>
        <span class="chip-label" style="color:{STAGE_TEXT_COLORS['混沌']};">混沌</span>
      </span>
      <span class="chip" style="background:{STAGE_CHIP_BG_COLORS['退潮']}; border-color:{STAGE_TEXT_COLORS['退潮']}33;">
        <span class="dot" style="background:{STAGE_TEXT_COLORS['退潮']}"></span>
        <span class="chip-label" style="color:{STAGE_TEXT_COLORS['退潮']};">退潮</span>
      </span>
    </div>
    <div class="card">
      <div class="top5-grid" id="top5-grid"></div>
      <div id="chart"></div>
    </div>
  </div>
  <script>
    const payload = {payload_json};
    const tradingDates = payload.x_labels;
    const latestSnapshot = payload.latest_snapshot || {{}};

    const latestSummaryParts = [];
    if (latestSnapshot.date) latestSummaryParts.push(`最新交易日: ${{latestSnapshot.date}}`);
    if (latestSnapshot.market_stage) latestSummaryParts.push(`阶段: ${{latestSnapshot.market_stage}}`);
    if (latestSnapshot.leader_direction_summary) latestSummaryParts.push(`主线方向: ${{latestSnapshot.leader_direction_summary}}`);
    if (latestSnapshot.top5_symbols && latestSnapshot.top5_symbols.length) latestSummaryParts.push(`Top5: ${{latestSnapshot.top5_symbols.join(" / ")}}`);
    document.getElementById("latest-summary").textContent = latestSummaryParts.join("  |  ");

    const top5Grid = document.getElementById("top5-grid");
    const top5Details = latestSnapshot.top5_details || [];
    top5Grid.innerHTML = top5Details.map((item) => `
      <div class="top5-item">
        <div><span class="top5-rank">${{item.rank}}</span><span class="top5-name">${{item.name}}</span></div>
        <div class="top5-symbol">${{item.symbol}}</div>
        <div class="top5-metric">
          今日涨幅: ${{Number(item.daily_return_pct || 0).toFixed(2)}}%<br>
          开收到收盘: ${{(Number(item.open_to_close_return || 0) * 100).toFixed(2)}}%<br>
          最高距收盘: ${{(Number(item.high_to_close_gap || 0) * 100).toFixed(2)}}%
        </div>
      </div>
    `).join("");

    const stageBands = payload.bands.map((band) => ({{
      type: "rect",
      xref: "x",
      yref: "paper",
      x0: band.start_idx - 0.5,
      x1: band.end_idx + 0.5,
      y0: 0,
      y1: 1,
      fillcolor: band.color,
      line: {{ width: 0 }},
      layer: "below"
    }}));

    const stageAnnotations = payload.bands.map((band) => ({{
      x: band.mid_idx,
      y: 0.985,
      xref: "x",
      yref: "paper",
      text: band.stage,
      showarrow: false,
      font: {{
        size: 13,
        color: ({{
          "主升": "{STAGE_TEXT_COLORS['主升']}",
          "启动": "{STAGE_TEXT_COLORS['启动']}",
          "混沌": "{STAGE_TEXT_COLORS['混沌']}",
          "退潮": "{STAGE_TEXT_COLORS['退潮']}"
        }})[band.stage] || "{STAGE_TEXT_COLORS['混沌']}"
      }},
      bgcolor: "rgba(255,253,247,0.72)",
      bordercolor: "rgba(229,220,203,0.65)",
      borderwidth: 1,
      borderpad: 4,
      opacity: 0.92
    }}));

    const traces = payload.traces.map((trace) => ({{
      type: "scatter",
      mode: "lines",
      name: trace.display_name || trace.name,
      x: trace.x,
      y: trace.y,
      customdata: trace.dates.map((date, idx) => [
        date,
        trace.stages[idx],
        trace.daily_return_pct[idx],
        trace.open_to_close_return[idx],
        trace.high_to_close_gap[idx]
      ]),
      visible: trace.visible ? true : "legendonly",
      line: {{
        width: trace.category === "market" ? 2.4 : 1.3,
        color: trace.color
      }},
      hovertemplate:
        "<b>%{{fullData.name}}</b><br>" +
        "日期: %{{customdata[0]}}<br>" +
        "阶段: %{{customdata[1]}}<br>" +
        "当日涨幅: %{{customdata[2]:.2f}}%<br>" +
        "开收到收盘: %{{customdata[3]:.2%}}<br>" +
        "最高距收盘: %{{customdata[4]:.2%}}<br>" +
        "归一化净值: %{{y:.3f}}<extra></extra>"
    }}));

    function computeTickConfig(rangeStart, rangeEnd) {{
      const safeStart = Math.max(0, Math.floor(rangeStart));
      const safeEnd = Math.min(tradingDates.length - 1, Math.ceil(rangeEnd));
      const visibleCount = Math.max(1, safeEnd - safeStart + 1);
      const detailed = visibleCount <= 40;
      const targetTicks = detailed ? 10 : 8;
      const step = Math.max(1, Math.ceil(visibleCount / targetTicks));
      const tickvals = [];
      const ticktext = [];
      for (let idx = safeStart; idx <= safeEnd; idx += step) {{
        tickvals.push(idx);
        ticktext.push(detailed ? tradingDates[idx] : tradingDates[idx].slice(0, 7));
      }}
      if (tickvals[tickvals.length - 1] !== safeEnd) {{
        tickvals.push(safeEnd);
        ticktext.push(detailed ? tradingDates[safeEnd] : tradingDates[safeEnd].slice(0, 7));
      }}
      return {{ tickvals, ticktext }};
    }}

    const initialRange = [Math.max(0, tradingDates.length - 250), tradingDates.length - 1];
    const initialTicks = computeTickConfig(initialRange[0], initialRange[1]);

    Plotly.newPlot("chart", traces, {{
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(255,255,255,0.78)",
      margin: {{ l: 60, r: 30, t: 30, b: 60 }},
      xaxis: {{
        title: "日期",
        type: "linear",
        showgrid: false,
        range: initialRange,
        tickmode: "array",
        tickvals: initialTicks.tickvals,
        ticktext: initialTicks.ticktext,
        rangeslider: {{ visible: true }}
      }},
      yaxis: {{
        title: "归一化净值",
        zeroline: false,
        gridcolor: "rgba(44, 62, 80, 0.10)"
      }},
      hovermode: "x unified",
      legend: {{
        orientation: "h",
        yanchor: "bottom",
        y: 1.02,
        xanchor: "left",
        x: 0
      }},
      shapes: stageBands,
      annotations: stageAnnotations
    }}, {{
      responsive: true,
      displaylogo: false
    }});

    const chart = document.getElementById("chart");
    chart.on("plotly_relayout", (eventData) => {{
      const range = eventData["xaxis.range"]
        || [eventData["xaxis.range[0]"], eventData["xaxis.range[1]"]];
      if (!range || range[0] == null || range[1] == null) {{
        return;
      }}
      const ticks = computeTickConfig(Number(range[0]), Number(range[1]));
      Plotly.relayout(chart, {{
        "xaxis.tickvals": ticks.tickvals,
        "xaxis.ticktext": ticks.ticktext
      }});
    }});
  </script>
</body>
</html>
"""
    output.write_text(html, encoding='utf-8')
    return output
