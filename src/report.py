"""HTML report generation for chess profiles."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .profiler import Profile

REPORT_DIR = Path(__file__).parent.parent / "reports"


def _bar(value: float, max_value: float, color: str = "#4CAF50") -> str:
    """Generate an inline CSS bar."""
    pct = (value / max_value * 100) if max_value else 0
    return f'<div class="bar" style="width:{pct:.0f}%;background:{color}"></div>'


def _wld_bar(wins: int, losses: int, draws: int) -> str:
    """Win/loss/draw stacked bar."""
    total = wins + losses + draws
    if not total:
        return ""
    wp = wins / total * 100
    lp = losses / total * 100
    dp = draws / total * 100
    return (
        f'<div class="stacked-bar">'
        f'<div class="bar-seg win" style="width:{wp:.1f}%"></div>'
        f'<div class="bar-seg loss" style="width:{lp:.1f}%"></div>'
        f'<div class="bar-seg draw" style="width:{dp:.1f}%"></div>'
        f'</div>'
    )


def _rating_sparkline(ratings: list[int]) -> str:
    """SVG sparkline for rating progression."""
    if len(ratings) < 2:
        return ""
    min_r = min(ratings)
    max_r = max(ratings)
    spread = max_r - min_r or 1
    w = 300
    h = 60
    points = []
    for i, r in enumerate(ratings):
        x = i / (len(ratings) - 1) * w
        y = h - (r - min_r) / spread * (h - 10) - 5
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    return (
        f'<svg width="{w}" height="{h}" class="sparkline">'
        f'<polyline points="{polyline}" fill="none" stroke="#2196F3" stroke-width="2"/>'
        f'<text x="0" y="{h}" class="spark-label">{ratings[0]}</text>'
        f'<text x="{w}" y="{h}" class="spark-label" text-anchor="end">{ratings[-1]}</text>'
        f'</svg>'
    )


def generate_html(profile: Profile, pattern_report=None, opening_recs=None) -> str:
    """Generate a self-contained HTML report."""
    avg_acc = profile.avg_accuracy()
    recent_acc = profile.recent_accuracy(20)

    sections = []

    # --- Header ---
    sections.append(f"""
    <div class="header">
        <h1>♟ {profile.username}</h1>
        <p class="subtitle">{profile.total_games} games analyzed</p>
    </div>
    """)

    # --- Summary cards ---
    overall = profile.overall
    cards = f"""
    <div class="cards">
        <div class="card">
            <div class="card-value">{overall.win_rate*100:.0f}%</div>
            <div class="card-label">Win Rate</div>
        </div>
        <div class="card">
            <div class="card-value">{overall.wins}</div>
            <div class="card-label">Wins</div>
        </div>
        <div class="card">
            <div class="card-value">{overall.losses}</div>
            <div class="card-label">Losses</div>
        </div>
        <div class="card">
            <div class="card-value">{overall.draws}</div>
            <div class="card-label">Draws</div>
        </div>
    """
    if avg_acc is not None:
        cards += f"""
        <div class="card">
            <div class="card-value">{avg_acc:.1f}%</div>
            <div class="card-label">Avg Accuracy</div>
        </div>
        """
    if recent_acc is not None:
        delta = recent_acc - avg_acc
        trend_class = "up" if delta > 0 else "down" if delta < 0 else ""
        cards += f"""
        <div class="card {trend_class}">
            <div class="card-value">{recent_acc:.1f}%</div>
            <div class="card-label">Recent Accuracy (20g)</div>
        </div>
        """
    cards += "</div>"
    sections.append(cards)

    # --- Rating progression ---
    if profile.rating_history:
        by_tc: dict[str, list[int]] = defaultdict(list)
        for _, tc, rating in profile.rating_history:
            by_tc[tc].append(rating)
        sparklines_html = ""
        for tc in sorted(by_tc):
            ratings = by_tc[tc]
            sparklines_html += f"""
            <div class="sparkline-row">
                <span class="tc-label">{tc}</span>
                <span class="rating-range">{min(ratings)} → {ratings[-1]}</span>
                {_rating_sparkline(ratings)}
            </div>
            """
        sections.append(f"""
        <div class="section">
            <h2>Rating Progression</h2>
            {sparklines_html}
        </div>
        """)

    # --- By Color ---
    sections.append('<div class="section"><h2>By Color</h2><table>')
    sections.append("<tr><th>Color</th><th>Record</th><th></th></tr>")
    for color in ("white", "black"):
        if color in profile.by_color:
            s = profile.by_color[color]
            sections.append(
                f"<tr><td>{color.capitalize()}</td>"
                f"<td>{s.wins}W / {s.losses}L / {s.draws}D ({s.win_rate*100:.0f}%)</td>"
                f"<td>{_wld_bar(s.wins, s.losses, s.draws)}</td></tr>"
            )
    sections.append("</table></div>")

    # --- By Time Control ---
    sections.append('<div class="section"><h2>By Time Control</h2><table>')
    sections.append("<tr><th>Format</th><th>Record</th><th></th></tr>")
    for tc in sorted(profile.by_time_class, key=lambda k: profile.by_time_class[k].total, reverse=True):
        s = profile.by_time_class[tc]
        sections.append(
            f"<tr><td>{tc}</td>"
            f"<td>{s.wins}W / {s.losses}L / {s.draws}D ({s.win_rate*100:.0f}%)</td>"
            f"<td>{_wld_bar(s.wins, s.losses, s.draws)}</td></tr>"
        )
    sections.append("</table></div>")

    # --- How You Lose ---
    if profile.loss_types:
        total_losses = sum(profile.loss_types.values())
        rows = ""
        for loss_type, count in sorted(profile.loss_types.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_losses * 100
            rows += (
                f"<tr><td>{loss_type}</td><td>{count} ({pct:.0f}%)</td>"
                f"<td>{_bar(count, total_losses, '#f44336')}</td></tr>"
            )
        sections.append(f"""
        <div class="section">
            <h2>How You Lose</h2>
            <table><tr><th>Type</th><th>Count</th><th></th></tr>
            {rows}
            </table>
        </div>
        """)

    # --- By Game Length ---
    length_order = ["short (≤15 moves)", "medium (16-30 moves)", "long (31+ moves)"]
    active_lengths = {k: v for k, v in profile.by_game_length.items() if v.total > 0}
    if active_lengths:
        rows = ""
        for length in length_order:
            if length in active_lengths:
                s = active_lengths[length]
                rows += (
                    f"<tr><td>{length}</td>"
                    f"<td>{s.wins}W / {s.losses}L / {s.draws}D ({s.win_rate*100:.0f}%)</td>"
                    f"<td>{_wld_bar(s.wins, s.losses, s.draws)}</td></tr>"
                )
        extra = ""
        win_moves = [m for m, r in profile.move_count_results if r == "win"]
        loss_moves = [m for m, r in profile.move_count_results if r == "loss"]
        if win_moves and loss_moves:
            extra = f"<p class='note'>Avg moves — wins: {sum(win_moves)/len(win_moves):.0f}, losses: {sum(loss_moves)/len(loss_moves):.0f}</p>"
        sections.append(f"""
        <div class="section">
            <h2>By Game Length</h2>
            <table><tr><th>Length</th><th>Record</th><th></th></tr>
            {rows}
            </table>
            {extra}
        </div>
        """)

    # --- Engine Analysis ---
    if profile.games_analyzed > 0:
        avg_blunders = profile.total_blunders / profile.games_analyzed
        avg_mistakes = profile.total_mistakes / profile.games_analyzed

        # Summary cards for engine stats
        sections.append(f"""
        <div class="cards">
            <div class="card" style="border-color:#f85149">
                <div class="card-value">{profile.total_blunders}</div>
                <div class="card-label">Blunders ({avg_blunders:.1f}/game)</div>
            </div>
            <div class="card" style="border-color:#d29922">
                <div class="card-value">{profile.total_mistakes}</div>
                <div class="card-label">Mistakes ({avg_mistakes:.1f}/game)</div>
            </div>
            <div class="card">
                <div class="card-value">{profile.total_inaccuracies}</div>
                <div class="card-label">Inaccuracies</div>
            </div>
            <div class="card">
                <div class="card-value">{profile.games_analyzed}</div>
                <div class="card-label">Games Analyzed</div>
            </div>
        </div>
        """)

        # Blunder types
        if profile.blunder_types:
            total_b = sum(profile.blunder_types.values())
            rows = ""
            for btype, count in sorted(profile.blunder_types.items(), key=lambda x: x[1], reverse=True):
                pct = count / total_b * 100
                label = btype.replace("_", " ").title()
                rows += (
                    f"<tr><td>{label}</td><td>{count} ({pct:.0f}%)</td>"
                    f"<td>{_bar(count, total_b, '#f85149')}</td></tr>"
                )
            sections.append(f"""
            <div class="section danger">
                <h2>Blunder Types</h2>
                <table><tr><th>Type</th><th>Count</th><th></th></tr>
                {rows}
                </table>
            </div>
            """)

        # Blunders by game phase
        if profile.blunder_phase:
            total_b = sum(profile.blunder_phase.values())
            rows = ""
            phase_order = ["opening (moves 1-10)", "middlegame (moves 11-25)", "endgame (moves 26+)"]
            for phase in phase_order:
                if phase in profile.blunder_phase:
                    count = profile.blunder_phase[phase]
                    pct = count / total_b * 100
                    rows += (
                        f"<tr><td>{phase}</td><td>{count} ({pct:.0f}%)</td>"
                        f"<td>{_bar(count, total_b, '#d29922')}</td></tr>"
                    )
            sections.append(f"""
            <div class="section">
                <h2>Blunders By Game Phase</h2>
                <table><tr><th>Phase</th><th>Count</th><th></th></tr>
                {rows}
                </table>
            </div>
            """)

        # Worst blunders
        if profile.worst_blunders:
            rows = ""
            for b in profile.worst_blunders[:5]:
                btype = (b["blunder_type"] or "other").replace("_", " ").title()
                best = f'Best: {b["best_move"]}' if b["best_move"] else ""
                link = b["game_url"]
                rows += (
                    f'<tr><td>Move {b["move_number"]}</td>'
                    f'<td>{b["move_san"]}</td>'
                    f'<td>-{b["cp_loss"]}cp</td>'
                    f'<td>{btype}</td>'
                    f'<td>{best}</td>'
                    f'<td><a href="{link}" target="_blank">View</a></td></tr>'
                )
            sections.append(f"""
            <div class="section danger">
                <h2>Top 5 Worst Blunders</h2>
                <table><tr><th>Move</th><th>Played</th><th>Loss</th><th>Type</th><th>Better</th><th></th></tr>
                {rows}
                </table>
            </div>
            """)

    # --- Weakest Openings ---
    openings = {
        name: stats for name, stats in profile.by_opening_and_color.items()
        if stats.total >= 2
    }
    if openings:
        worst = sorted(openings.items(), key=lambda x: x[1].win_rate)[:10]
        rows = ""
        for name, s in worst:
            rows += (
                f"<tr><td>{name}</td>"
                f"<td>{s.wins}W / {s.losses}L / {s.draws}D ({s.win_rate*100:.0f}%)</td>"
                f"<td>{_wld_bar(s.wins, s.losses, s.draws)}</td></tr>"
            )
        sections.append(f"""
        <div class="section danger">
            <h2>⚠ Weakest Openings (2+ games)</h2>
            <table><tr><th>Opening</th><th>Record</th><th></th></tr>
            {rows}
            </table>
        </div>
        """)

        best = sorted(openings.items(), key=lambda x: x[1].win_rate, reverse=True)[:10]
        rows = ""
        for name, s in best:
            rows += (
                f"<tr><td>{name}</td>"
                f"<td>{s.wins}W / {s.losses}L / {s.draws}D ({s.win_rate*100:.0f}%)</td>"
                f"<td>{_wld_bar(s.wins, s.losses, s.draws)}</td></tr>"
            )
        sections.append(f"""
        <div class="section success">
            <h2>✓ Strongest Openings (2+ games)</h2>
            <table><tr><th>Opening</th><th>Record</th><th></th></tr>
            {rows}
            </table>
        </div>
        """)

    # --- Pattern Analysis ---
    if pattern_report and pattern_report.total_blunders > 0:
        # Piece moved when blundering
        if pattern_report.piece_moved:
            total = sum(pattern_report.piece_moved.values())
            rows = ""
            for piece, count in sorted(pattern_report.piece_moved.items(), key=lambda x: x[1], reverse=True):
                pct = count / total * 100
                rows += (
                    f"<tr><td>{piece.title()}</td><td>{count} ({pct:.0f}%)</td>"
                    f"<td>{_bar(count, total, '#d29922')}</td></tr>"
                )
            sections.append(f"""
            <div class="section">
                <h2>Piece Moved When Blundering</h2>
                <table><tr><th>Piece</th><th>Count</th><th></th></tr>
                {rows}
                </table>
            </div>
            """)

        # Tactical motifs missed
        if pattern_report.motifs:
            total = sum(pattern_report.motifs.values())
            rows = ""
            for motif, count in sorted(pattern_report.motifs.items(), key=lambda x: x[1], reverse=True):
                pct = count / total * 100
                rows += (
                    f"<tr><td>{motif.title()}</td><td>{count} ({pct:.0f}%)</td>"
                    f"<td>{_bar(count, total, '#58a6ff')}</td></tr>"
                )
            sections.append(f"""
            <div class="section">
                <h2>What You're Missing (Best Move Was)</h2>
                <table><tr><th>Motif</th><th>Count</th><th></th></tr>
                {rows}
                </table>
            </div>
            """)

        # Position context when blundering
        if pattern_report.eval_context:
            total = sum(pattern_report.eval_context.values())
            rows = ""
            colors = {"winning": "#238636", "even": "#8b949e", "losing": "#f85149"}
            for ctx in ["winning", "even", "losing"]:
                if ctx in pattern_report.eval_context:
                    count = pattern_report.eval_context[ctx]
                    pct = count / total * 100
                    rows += (
                        f"<tr><td>{ctx.title()}</td><td>{count} ({pct:.0f}%)</td>"
                        f"<td>{_bar(count, total, colors.get(ctx, '#8b949e'))}</td></tr>"
                    )
            sections.append(f"""
            <div class="section">
                <h2>Position When Blundering</h2>
                <table><tr><th>Context</th><th>Count</th><th></th></tr>
                {rows}
                </table>
            </div>
            """)

        # Key insights
        from .patterns import _generate_insights
        insights = _generate_insights(pattern_report)
        if insights:
            insight_items = "".join(f"<li>{i}</li>" for i in insights)
            sections.append(f"""
            <div class="section" style="border-color:#58a6ff44">
                <h2>Key Insights</h2>
                <ul style="list-style:none;padding:0">
                {insight_items}
                </ul>
            </div>
            """)

    # --- Opening Recommendations ---
    if opening_recs:
        problems = [r for r in opening_recs if r.win_rate < 0.5]
        strengths = [r for r in opening_recs if r.win_rate >= 0.5]

        if problems:
            rows = ""
            for r in problems:
                rows += (
                    f"<tr><td>{r.name}<br><small style='color:#8b949e'>as {r.color}</small></td>"
                    f"<td>{r.games_played}</td>"
                    f"<td>{r.win_rate*100:.0f}%</td>"
                    f"<td>{r.suggestion}</td></tr>"
                )
            sections.append(f"""
            <div class="section danger">
                <h2>Openings to Study</h2>
                <table><tr><th>Opening</th><th>Games</th><th>Win%</th><th>Recommendation</th></tr>
                {rows}
                </table>
            </div>
            """)

        if strengths:
            rows = ""
            for r in strengths:
                rows += (
                    f"<tr><td>{r.name}<br><small style='color:#8b949e'>as {r.color}</small></td>"
                    f"<td>{r.games_played}</td>"
                    f"<td>{r.win_rate*100:.0f}%</td>"
                    f"<td>{r.suggestion}</td></tr>"
                )
            sections.append(f"""
            <div class="section success">
                <h2>Your Best Openings — Keep Playing These</h2>
                <table><tr><th>Opening</th><th>Games</th><th>Win%</th><th>Recommendation</th></tr>
                {rows}
                </table>
            </div>
            """)

    body = "\n".join(sections)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chess Profile: {profile.username}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #0d1117;
    color: #e6edf3;
    padding: 2rem;
    max-width: 900px;
    margin: 0 auto;
}}
.header {{ text-align: center; margin-bottom: 2rem; }}
.header h1 {{ font-size: 2rem; color: #58a6ff; }}
.subtitle {{ color: #8b949e; margin-top: 0.5rem; }}
.cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}}
.card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
}}
.card.up {{ border-color: #238636; }}
.card.down {{ border-color: #f85149; }}
.card-value {{ font-size: 1.5rem; font-weight: bold; color: #f0f6fc; }}
.card-label {{ font-size: 0.8rem; color: #8b949e; margin-top: 0.25rem; }}
.section {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}}
.section.danger {{ border-color: #f8514944; }}
.section.success {{ border-color: #23863644; }}
h2 {{ font-size: 1.1rem; color: #58a6ff; margin-bottom: 1rem; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; color: #8b949e; font-weight: normal; font-size: 0.85rem; padding: 0.5rem; border-bottom: 1px solid #30363d; }}
td {{ padding: 0.5rem; border-bottom: 1px solid #21262d; }}
.stacked-bar {{
    display: flex;
    height: 16px;
    border-radius: 4px;
    overflow: hidden;
    min-width: 100px;
}}
.bar-seg {{ height: 100%; }}
.bar-seg.win {{ background: #238636; }}
.bar-seg.loss {{ background: #f85149; }}
.bar-seg.draw {{ background: #8b949e; }}
.bar {{
    height: 16px;
    border-radius: 4px;
    min-width: 2px;
}}
.sparkline {{ display: block; margin-top: 0.5rem; }}
.spark-label {{ fill: #8b949e; font-size: 11px; }}
.sparkline-row {{
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
}}
.tc-label {{ font-weight: bold; min-width: 60px; }}
.rating-range {{ color: #8b949e; font-size: 0.85rem; min-width: 80px; }}
.note {{ color: #8b949e; font-size: 0.85rem; margin-top: 0.75rem; }}
li {{ padding: 0.5rem 0; border-bottom: 1px solid #21262d; color: #e6edf3; }}
li:last-child {{ border-bottom: none; }}
footer {{ text-align: center; color: #484f58; margin-top: 2rem; font-size: 0.8rem; }}
</style>
</head>
<body>
{body}
<footer>Generated by chess-profiler · {now}</footer>
</body>
</html>"""


def save_report(profile: Profile, fmt: str = "html",
                pattern_report=None, opening_recs=None) -> Path:
    """Save a profile report and return the file path."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt == "html":
        path = REPORT_DIR / f"{profile.username}_{timestamp}.html"
        path.write_text(generate_html(profile, pattern_report, opening_recs))
    else:
        from .profiler import format_profile
        from .patterns import format_patterns
        from .openings import format_recommendations
        parts = [format_profile(profile)]
        if pattern_report:
            parts.append(format_patterns(pattern_report))
        if opening_recs:
            parts.append(format_recommendations(opening_recs))
        path = REPORT_DIR / f"{profile.username}_{timestamp}.txt"
        path.write_text("\n\n".join(parts))

    return path
