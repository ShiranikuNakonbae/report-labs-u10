"""Render a parsed team report into the final HTML report.

This is a faithful, team-agnostic port of the rendering logic in
``statistik_labs_u10.ipynb``. It consumes the dictionary produced by
``parser.compute_team_report`` and returns a complete HTML document.
"""

from datetime import datetime
from html import escape


def _format_percent(value):
    return "N/A" if value is None else f"{value * 100:.1f}%"


def _format_improvement(value):
    return "N/A" if value is None else f"{value:+.1f}%"


def _table(headers, rows, keys):
    """Generic table where ``rows`` are dicts and ``keys`` is the column order."""
    header_html = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row.get(k, '')))}</td>" for k in keys) + "</tr>"
        for row in rows
    )
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody></table>"
    )


def _player_table(rows):
    keys = [
        "player", "games", "ab", "runs", "hits", "rbi", "errors",
        "pa", "avg", "obp_proxy", "hit_score",
    ]
    headers = ["Pemain", "Game", "AB", "R", "H", "RBI", "E", "PA", "AVG", "OBP proxy", "Hit score"]
    header_html = "".join(
        f"<th class='sortable' data-column='{i}' data-type='{'text' if i == 0 else 'number'}'>"
        f"{escape(h)}<span class='sort-indicator'>↕</span></th>"
        for i, h in enumerate(headers)
    )
    body_html = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row[k]))}</td>" for k in keys) + "</tr>"
        for row in rows
    )
    return (
        f"<table id='player-profile-table' class='sortable-table'><thead><tr>"
        f"{header_html}</tr></thead><tbody>{body_html}</tbody></table>"
    )


def _bar_chart(rows, metric, label, color):
    selected = sorted(rows, key=lambda row: row[metric], reverse=True)[:10]
    maximum = max((row[metric] for row in selected), default=1) or 1
    bars = []
    for row in selected:
        width = row[metric] / maximum * 100
        bars.append(
            f"<div class='bar-row'><span>{escape(row['player'])}</span>"
            f"<div class='bar-track'><i style='width:{width:.1f}%;background:{color}'></i></div>"
            f"<b>{row[metric]}</b></div>"
        )
    return f"<section class='chart'><h3>{label}</h3>{''.join(bars)}</section>"


def _obp_chart(player, trend_by_player, game_numbers, opponents_by_game):
    values = trend_by_player[player]
    chart_width, chart_height = 560, 220
    plot_left, plot_right = 54, 530
    plot_top, plot_bottom = 18, 158
    x_step = (plot_right - plot_left) / max(len(game_numbers) - 1, 1)

    points, circles, segments = [], [], []
    for index, game in enumerate(game_numbers):
        value = values.get(game)
        x = plot_left + index * x_step
        if value is None:
            continue
        y = plot_bottom - value * (plot_bottom - plot_top)
        points.append((x, y))
        circles.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' />")
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        segments.append(f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' />")

    grid = []
    for tick in (0, 25, 50, 75, 100):
        y = plot_bottom - tick / 100 * (plot_bottom - plot_top)
        grid.append(
            f"<line class='grid-line' x1='{plot_left}' y1='{y:.1f}' x2='{plot_right}' y2='{y:.1f}' />"
            f"<text class='axis-label' x='8' y='{y + 4:.1f}'>{tick}%</text>"
        )

    x_labels = []
    for index, game in enumerate(game_numbers):
        x = plot_left + index * x_step
        x_labels.append(
            f"<text class='x-label' x='{x:.1f}' y='184' text-anchor='middle'>"
            f"{escape(opponents_by_game[game])}</text>"
        )
        x_labels.append(f"<text class='game-label' x='{x:.1f}' y='202' text-anchor='middle'>G{game}</text>")

    return (
        f"<section class='obp-chart'><h3>{escape(player)}</h3>"
        f"<svg viewBox='0 0 {chart_width} {chart_height}' role='img' aria-label='Trend OBP {escape(player)}'>"
        f"{''.join(grid)}"
        f"<line class='axis' x1='{plot_left}' y1='{plot_bottom}' x2='{plot_right}' y2='{plot_bottom}' />"
        f"<line class='axis' x1='{plot_left}' y1='{plot_top}' x2='{plot_left}' y2='{plot_bottom}' />"
        f"{''.join(segments)}{''.join(circles)}{''.join(x_labels)}</svg></section>"
    )


def _slugging_chart(player, slugging_by_player, game_numbers, opponents_by_game, axis_max):
    values = slugging_by_player[player]
    chart_width, chart_height = 560, 220
    plot_left, plot_right = 54, 530
    plot_top, plot_bottom = 18, 158
    x_step = (plot_right - plot_left) / max(len(game_numbers) - 1, 1)

    points, circles, segments = [], [], []
    for index, game in enumerate(game_numbers):
        value = values.get(game)
        x = plot_left + index * x_step
        if value is None:
            continue
        y = plot_bottom - min(value / axis_max, 1) * (plot_bottom - plot_top)
        points.append((x, y))
        circles.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' />")
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        segments.append(f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' />")

    grid = []
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        y = plot_bottom - fraction * (plot_bottom - plot_top)
        tick_value = axis_max * fraction
        grid.append(
            f"<line class='grid-line' x1='{plot_left}' y1='{y:.1f}' x2='{plot_right}' y2='{y:.1f}' />"
            f"<text class='axis-label' x='8' y='{y + 4:.1f}'>{tick_value:.2f}</text>"
        )

    x_labels = []
    for index, game in enumerate(game_numbers):
        x = plot_left + index * x_step
        x_labels.append(
            f"<text class='x-label' x='{x:.1f}' y='184' text-anchor='middle'>"
            f"{escape(opponents_by_game[game])}</text>"
        )
        x_labels.append(f"<text class='game-label' x='{x:.1f}' y='202' text-anchor='middle'>G{game}</text>")

    return (
        f"<section class='slug-chart'><h3>{escape(player)}</h3>"
        f"<svg viewBox='0 0 {chart_width} {chart_height}' role='img' aria-label='Trend slugging {escape(player)}'>"
        f"{''.join(grid)}"
        f"<line class='axis' x1='{plot_left}' y1='{plot_bottom}' x2='{plot_right}' y2='{plot_bottom}' />"
        f"<line class='axis' x1='{plot_left}' y1='{plot_top}' x2='{plot_left}' y2='{plot_bottom}' />"
        f"{''.join(segments)}{''.join(circles)}{''.join(x_labels)}</svg></section>"
    )


_CSS = """\
:root { --ink:#16232d; --muted:#60717b; --line:#d9e1e5; --paper:#f7faf8; --accent:#117a65; --gold:#e6a23c; }
* { box-sizing:border-box; } body { margin:0; color:var(--ink); background:var(--paper); font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }
main { max-width:1180px; margin:0 auto; padding:42px 28px 64px; } header { border-bottom:4px solid var(--accent); padding-bottom:24px; margin-bottom:26px; }
h1 { margin:0 0 6px; font-size:34px; } h2 { margin:34px 0 12px; font-size:22px; } h3 { margin:0 0 12px; font-size:16px; } .subtitle,.note { color:var(--muted); }
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:22px 0 30px; } .kpi { background:#fff; border:1px solid var(--line); border-top:4px solid var(--accent); padding:15px; } .kpi b { display:block; font-size:28px; }
table { width:100%; border-collapse:collapse; background:#fff; margin:10px 0 18px; } th,td { border:1px solid var(--line); padding:8px 10px; text-align:right; white-space:nowrap; } th { background:#e9f1ed; color:#25443c; } th:first-child,td:first-child,th:nth-child(2),td:nth-child(2) { text-align:left; }
.sortable { cursor:pointer; user-select:none; } .sortable:hover { background:#d9e9e2; } .sort-indicator { color:var(--muted); font-size:11px; margin-left:5px; } .sortable[aria-sort='ascending'] .sort-indicator::after { content:' \\2191'; color:var(--accent); } .sortable[aria-sort='descending'] .sort-indicator::after { content:' \\2193'; color:var(--accent); }
.positive { color:#117a65; font-weight:700; } .negative { color:#b94b4b; font-weight:700; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:22px; } .chart { background:#fff; border:1px solid var(--line); padding:16px; } .bar-row { display:grid; grid-template-columns:145px 1fr 48px; align-items:center; gap:8px; margin:9px 0; } .bar-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } .bar-track { height:13px; background:#edf1ef; } .bar-track i { display:block; height:100%; } .method { background:#fff; border-left:4px solid var(--gold); padding:15px 18px; }
@media(max-width:650px) { main { padding:25px 14px; } h1 { font-size:27px; } table { display:block; overflow-x:auto; } .bar-row { grid-template-columns:105px 1fr 42px; } }
.obp-chart-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(420px,1fr)); gap:18px; } .obp-chart { background:#fff; border:1px solid var(--line); padding:14px 12px 10px; } .obp-chart h3 { margin:0 0 4px; color:var(--ink); } .obp-chart svg { width:100%; height:auto; overflow:visible; } .obp-chart .grid-line { stroke:#e7ece9; stroke-width:1; } .obp-chart .axis { stroke:#718078; stroke-width:1.2; } .obp-chart line:not(.grid-line):not(.axis) { stroke:#117a65; stroke-width:2.5; } .obp-chart circle { fill:#117a65; stroke:#fff; stroke-width:2; } .obp-chart .axis-label,.obp-chart .x-label,.obp-chart .game-label { fill:#60717b; font:11px system-ui,sans-serif; }
.slug-chart-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(420px,1fr)); gap:18px; } .slug-chart { background:#fff; border:1px solid var(--line); padding:14px 12px 10px; } .slug-chart h3 { margin:0 0 4px; color:var(--ink); } .slug-chart svg { width:100%; height:auto; overflow:visible; } .slug-chart .grid-line { stroke:#f0dfc4; stroke-width:1; } .slug-chart .axis { stroke:#718078; stroke-width:1.2; } .slug-chart line:not(.grid-line):not(.axis) { stroke:#d88728; stroke-width:2.5; } .slug-chart circle { fill:#d88728; stroke:#fff; stroke-width:2; } .slug-chart .axis-label,.slug-chart .x-label,.slug-chart .game-label { fill:#60717b; font:11px system-ui,sans-serif; }
.slug-total-chart { background:#fff; border:1px solid var(--line); padding:16px; max-width:760px; } .slug-total-row { display:grid; grid-template-columns:170px 1fr 64px; align-items:center; gap:10px; margin:9px 0; } .slug-total-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } .slug-total-track { height:14px; background:#f5eadb; } .slug-total-track i { display:block; height:100%; background:#d88728; }
"""

_SORTABLE_SCRIPT = """\
<script>
['#player-profile-table', '#improvement-table'].forEach(function (id) {
  var table = document.querySelector(id);
  if (!table) return;
  table.querySelectorAll('th.sortable').forEach(function (header) {
    header.addEventListener('click', function () {
      var tbody = table.querySelector('tbody');
      var column = Number(header.dataset.column);
      var type = header.dataset.type;
      var ascending = header.getAttribute('aria-sort') !== 'ascending';
      table.querySelectorAll('th.sortable').forEach(function (h) { h.removeAttribute('aria-sort'); });
      header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
      Array.from(tbody.querySelectorAll('tr')).sort(function (a, b) {
        var av = a.children[column].textContent.trim();
        var bv = b.children[column].textContent.trim();
        var cmp;
        if (type === 'number') {
          var an = av === 'N/A' ? Number.NEGATIVE_INFINITY : Number(av.replace('%', '').replace('+', ''));
          var bn = bv === 'N/A' ? Number.NEGATIVE_INFINITY : Number(bv.replace('%', '').replace('+', ''));
          cmp = an - bn;
        } else {
          cmp = av.localeCompare(bv);
        }
        return ascending ? cmp : -cmp;
      }).forEach(function (row) { tbody.appendChild(row); });
    });
  });
});
</script>
"""


def render_report(report, source_name, generated_at=None):
    """Return a complete HTML report string for a single team's statistics."""
    team = report["team"]
    generated_at = generated_at or datetime.now()

    game_rows = report["game_rows"]
    player_rows = report["player_rows"]
    game_numbers = report["game_numbers"]
    opponents_by_game = report["opponents_by_game"]
    trend_by_player = report["trend_by_player"]
    slugging_by_player = report["slugging_by_player"]
    wins = report["wins"]
    total_games = len(game_rows)

    # --- Game summary table ---
    game_table = _table(
        ["Game", "Matchup", "Opponent", "Result",
         f"{team} R", f"{team} H", f"{team} E", "Opp R"],
        [{
            "Game": row["game"],
            "Matchup": row["matchup"],
            "Opponent": row["opponent"],
            "Result": row["result"],
            f"{team} R": row["team_runs"],
            f"{team} H": row["team_hits"],
            f"{team} E": row["team_errors"],
            "Opp R": row["opp_runs"],
        } for row in game_rows],
        ["Game", "Matchup", "Opponent", "Result",
         f"{team} R", f"{team} H", f"{team} E", "Opp R"],
    )

    # --- Player profile table (sorted by hit score, then OBP) ---
    sorted_players = sorted(
        player_rows, key=lambda row: (row["hit_score"], row["obp_proxy"]), reverse=True
    )

    # --- Bar charts ---
    bar_charts = (
        _bar_chart(player_rows, "obp_proxy", "Top OBP proxy", "#117a65")
        + _bar_chart(player_rows, "hit_score", "Top hit score", "#e6a23c")
        + _bar_chart(player_rows, "hits", "Top hit", "#4378a8")
    )

    # --- Slugging section ---
    slugging_total_rows = sorted(player_rows, key=lambda row: row["slugging_average"], reverse=True)
    slugging_axis_max = max((row["slugging_average"] for row in slugging_total_rows), default=1) or 1
    slugging_chart_grid = "".join(
        _slugging_chart(p, slugging_by_player, game_numbers, opponents_by_game, slugging_axis_max)
        for p in sorted(slugging_by_player)
    )
    slugging_total_bars = "".join(
        f"<div class='slug-total-row'><span>{escape(row['player'])}</span>"
        f"<div class='slug-total-track'><i style='width:{min(row['slugging_average'] / slugging_axis_max * 100, 100):.1f}%'></i></div>"
        f"<b>{row['slugging_average']:.3f}</b></div>"
        for row in slugging_total_rows
    )
    slugging_section = (
        "<h2>Grafik Slugging Average</h2>"
        "<p class='note'>Slugging average = total bases / AB. Bobot total bases: single 1, double 2, triple 3, home run 4. "
        "Kedua grafik memakai skala Y yang sama berdasarkan slugging average total tertinggi.</p>"
        "<h3>Slugging average per pemain per pertandingan</h3>"
        f"<div class='slug-chart-grid'>{slugging_chart_grid}</div>"
        "<h3>Total slugging average seluruh pertandingan</h3>"
        f"<section class='slug-total-chart'>{slugging_total_bars}</section>"
    )

    # --- OBP trend charts ---
    obp_chart_grid = "".join(
        _obp_chart(p, trend_by_player, game_numbers, opponents_by_game)
        for p in sorted(trend_by_player)
    )
    obp_section = (
        "<h2>Grafik Trend OBP per Pertandingan</h2>"
        "<p class='note'>Sumbu X menunjukkan lawan aktual pada setiap pertandingan. Sumbu Y menunjukkan OBP proxy dalam persen. "
        "Game yang tidak diikuti pemain dibiarkan kosong.</p>"
        f"<div class='obp-chart-grid'>{obp_chart_grid}</div>"
    )

    # --- Improvement table ---
    improvement_headers = [
        "Pemain", "Game awal", "Game akhir", "OBP awal", "OBP akhir", "Improvement OBP",
        "Hit ratio awal", "Hit ratio akhir", "Improvement hit ratio",
    ]
    improvement_header_html = "".join(
        f"<th class='sortable' data-column='{i}' data-type='{'text' if i == 0 else 'number'}'>"
        f"{escape(h)}<span class='sort-indicator'>↕</span></th>"
        for i, h in enumerate(improvement_headers)
    )
    improvement_body = "".join(
        "<tr>"
        f"<td>{escape(row['player'])}</td>"
        f"<td>{row['first_game']}</td><td>{row['last_game']}</td>"
        f"<td>{_format_percent(row['obp_first'])}</td><td>{_format_percent(row['obp_last'])}</td>"
        f"<td class='{'positive' if row['obp_improvement'] is not None and row['obp_improvement'] >= 0 else 'negative'}'>{_format_improvement(row['obp_improvement'])}</td>"
        f"<td>{_format_percent(row['hit_ratio_first'])}</td><td>{_format_percent(row['hit_ratio_last'])}</td>"
        f"<td class='{'positive' if row['hit_ratio_improvement'] is not None and row['hit_ratio_improvement'] >= 0 else 'negative'}'>{_format_improvement(row['hit_ratio_improvement'])}</td>"
        "</tr>"
        for row in report["improvement_rows"]
    )
    improvement_table = (
        "<table id='improvement-table' class='sortable-table'><thead><tr>"
        f"{improvement_header_html}</tr></thead><tbody>{improvement_body}</tbody></table>"
    )

    # --- Defensive error analysis ---
    error_game_table = _table(
        ["Game", "Lawan", "Total error", "Event error eksplisit"],
        [{
            "Game": row["game"],
            "Lawan": row["opponent"],
            "Total error": row["errors"],
            "Event error eksplisit": report["error_events_by_game"][row["game"]],
        } for row in report["error_game_rows"]],
        ["Game", "Lawan", "Total error", "Event error eksplisit"],
    )
    error_player_table = _table(
        ["Game", "Lawan", "Pemain", "Posisi", "Error"],
        [{
            "Game": row["game"],
            "Lawan": row["opponent"],
            "Pemain": row["player"],
            "Posisi": row["position"],
            "Error": row["errors"],
        } for row in report["error_player_rows"]],
        ["Game", "Lawan", "Pemain", "Posisi", "Error"],
    )
    player_frequency_table = _table(
        ["Pemain", "Total error"],
        [{"Pemain": player, "Total error": count}
         for player, count in report["error_player_totals"].most_common()],
        ["Pemain", "Total error"],
    )
    position_table = _table(
        ["Posisi", "Total error"],
        [{"Posisi": pos, "Total error": count}
         for pos, count in report["error_position_totals"].most_common()],
        ["Posisi", "Total error"],
    )

    runs_after_error_rows = report["runs_after_error_rows"]
    runs_after_error_total_table = _table(
        ["Game", "Lawan", "Total run pada inning dengan error"],
        [{
            "Game": row["game"],
            "Lawan": row["opponent"],
            "Total run pada inning dengan error": sum(
                item["runs"] for item in runs_after_error_rows if item["game"] == row["game"]
            ),
        } for row in report["error_game_rows"]],
        ["Game", "Lawan", "Total run pada inning dengan error"],
    )
    runs_after_error_table = _table(
        ["Game", "Lawan", "Inning", "Run lawan pada inning dengan error"],
        [{
            "Game": row["game"],
            "Lawan": row["opponent"],
            "Inning": row["inning"],
            "Run lawan pada inning dengan error": row["runs"],
        } for row in runs_after_error_rows],
        ["Game", "Lawan", "Inning", "Run lawan pada inning dengan error"],
    )

    error_section = (
        "<h2>Analisis Defensive Error</h2>"
        "<p class='note'>Total error berasal dari baris E pada box score. Analisis ini menampilkan ringkasan "
        "per pertandingan, pemain, posisi, frekuensi tertinggi, dan run lawan pada inning dengan error.</p>"
        "<h3>Error per pertandingan</h3>" + error_game_table
        + "<h3>Error per pemain dan posisi</h3>" + error_player_table
        + "<div class='grid'><section><h3>Frekuensi pemain tertinggi</h3>" + player_frequency_table
        + "</section><section><h3>Posisi paling bermasalah</h3>" + position_table + "</section></div>"
        "<h3>Run lawan setelah error</h3>"
        "<p class='note'>Angka ini adalah total run lawan pada inning defensif " + escape(team)
        + " yang mengandung minimal satu event error eksplisit. Karena PDF tidak selalu menyatakan urutan "
        "waktu setiap event, angka ini dibaca sebagai run pada inning yang sama, bukan klaim kausal per error tunggal.</p>"
        + runs_after_error_total_table + runs_after_error_table
    )

    # --- Metodologi ---
    methodology = (
        "<h2>Metodologi</h2><div class='method'>"
        "<p><b>AVG</b> = H / AB.</p>"
        "<p><b>OBP proxy</b> = event yang mencapai base (hit, reached on error, fielder choice, HBP/walk bila tertulis) / plate appearance dari play-by-play.</p>"
        "<p><b>Hit score</b> menggunakan bobot presentasi contoh: HR 100, triple 90, double 80, single 70, HBP 70, reach 50, out 50, strikeout 40.</p>"
        "<p>Game dengan matchup dan isi box score identik dihitung sekali.</p>"
        "</div>"
    )

    kpis = (
        "<div class='kpis'>"
        f"<div class='kpi'><span>Game unik</span><b>{total_games}</b></div>"
        f"<div class='kpi'><span>Rekor</span><b>{wins}-{total_games - wins}</b></div>"
        f"<div class='kpi'><span>Total run {escape(team)}</span><b>{report['total_runs']}</b></div>"
        f"<div class='kpi'><span>Total hit {escape(team)}</span><b>{report['total_hits']}</b></div>"
        f"<div class='kpi'><span>Pemain</span><b>{report['player_count']}</b></div>"
        "</div>"
    )

    return f"""<!doctype html>
<html lang='id'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(team)} | Statistical Game and Player Report</title>
<style>{_CSS}</style></head><body><main>
<header><h1>{escape(team)}</h1><div class='subtitle'>Statistical Game and Player Report | sumber: {escape(source_name)}</div><div class='subtitle'>Dibuat {generated_at:%d %B %Y %H:%M}</div></header>
{kpis}
<h2>Ringkasan pertandingan</h2>{game_table}
<h2>Profil pemain</h2><p class='note'>Klik header tabel untuk mengurutkan. Klik lagi untuk membalik ascending/descending.</p>{_player_table(sorted_players)}
<div class='grid'>{bar_charts}</div>
{slugging_section}
{obp_section}
<h2>Improvement OBP dan Hit Ratio</h2><p class='note'>Klik header untuk sorting ascending/descending. Improvement = (nilai akhir - nilai awal) / nilai awal x 100. N/A berarti nilai awal nol.</p>{improvement_table}
{error_section}
{methodology}
{_SORTABLE_SCRIPT}
</main></body></html>"""
