"""Daily review — focused analysis of a single day's games."""

from datetime import datetime, timedelta
from pathlib import Path

import chess
import chess.svg

from .models import Game
from .engine import GameAnalysis, MoveAnalysis, analyze_games

REPORT_DIR = Path(__file__).parent.parent / "reports"


def filter_games_by_date(games: list[Game], date: str) -> list[Game]:
    """Filter games to a specific date (format: YYYY.MM.DD)."""
    return [g for g in games if g.date == date]


def get_key_mistake(analysis: GameAnalysis, color: str) -> MoveAnalysis | None:
    """Find the single worst mistake in a game for the given color."""
    player_moves = [m for m in analysis.moves if m.color == color and m.cp_loss > 0]
    if not player_moves:
        return None
    return max(player_moves, key=lambda m: m.cp_loss)


def generate_review(games: list[Game], analyses: list[GameAnalysis],
                    username: str, date: str) -> str:
    """Generate a text daily review."""
    if not games:
        return f"No games found for {date}."

    analysis_by_url = {a.game_url: a for a in analyses}

    lines = []
    lines.append(f"=== Daily Review: {date} ===")
    lines.append(f"{len(games)} games played")
    lines.append("")

    wins = sum(1 for g in games if g.player_result(username) == "win")
    losses = sum(1 for g in games if g.player_result(username) == "loss")
    draws = sum(1 for g in games if g.player_result(username) == "draw")
    lines.append(f"Results: {wins}W / {losses}L / {draws}D")
    lines.append("")

    # Per-game breakdown
    all_mistakes = []
    for i, game in enumerate(games, 1):
        color = game.player_color(username)
        result = game.player_result(username)
        opponent = game.opponent_username(username)
        result_icon = {"win": "+", "loss": "-", "draw": "="}[result]

        lines.append(f"Game {i}: [{result_icon}] vs {opponent} ({game.time_class})")
        lines.append(f"  Opening: {game.opening or 'Unknown'}")
        lines.append(f"  You played: {color}")

        acc = game.player_accuracy(username)
        if acc is not None:
            lines.append(f"  Accuracy: {acc:.1f}%")

        # Key mistake
        analysis = analysis_by_url.get(game.url)
        if analysis:
            mistake = get_key_mistake(analysis, color)
            if mistake:
                all_mistakes.append(mistake)
                best = f", best: {mistake.best_move_san}" if mistake.best_move_san else ""
                btype = f" ({mistake.blunder_type.replace('_', ' ')})" if mistake.blunder_type else ""
                lines.append(f"  Key mistake: Move {mistake.move_number} {mistake.move_san} "
                             f"(-{mistake.cp_loss}cp{btype}{best})")
            else:
                lines.append("  Key mistake: None — clean game!")
        lines.append("")

    # Pattern across mistakes
    if all_mistakes:
        lines.append("--- Pattern Across Today's Games ---")
        blunder_count = sum(1 for m in all_mistakes if m.category == "blunder")
        mistake_count = sum(1 for m in all_mistakes if m.category == "mistake")
        avg_loss = sum(m.cp_loss for m in all_mistakes) / len(all_mistakes)
        lines.append(f"  Worst moves: {blunder_count} blunders, {mistake_count} mistakes")
        lines.append(f"  Average cp loss on worst move: {avg_loss:.0f}")

        # Phase of worst moves
        phases = {"opening": 0, "middlegame": 0, "endgame": 0}
        for m in all_mistakes:
            if m.move_number <= 10:
                phases["opening"] += 1
            elif m.move_number <= 25:
                phases["middlegame"] += 1
            else:
                phases["endgame"] += 1
        worst_phase = max(phases, key=phases.get)
        lines.append(f"  Most mistakes in: {worst_phase}")

        # Types
        types = {}
        for m in all_mistakes:
            if m.blunder_type:
                t = m.blunder_type.replace("_", " ")
                types[t] = types.get(t, 0) + 1
        if types:
            worst_type = max(types, key=types.get)
            lines.append(f"  Most common issue: {worst_type}")

        lines.append("")
        lines.append("  Takeaway: ", )
        if avg_loss > 500:
            lines.append("    Big swings today. Focus on checking for hanging pieces before every move.")
        elif avg_loss > 200:
            lines.append("    Moderate mistakes. Slow down on critical moves — check captures and checks first.")
        else:
            lines.append("    Solid day. Keep it up — your mistakes were minor.")

    return "\n".join(lines)


def generate_review_html(games: list[Game], analyses: list[GameAnalysis],
                         username: str, date: str) -> str:
    """Generate an HTML daily review."""
    if not games:
        return "<html><body><h1>No games found</h1></body></html>"

    analysis_by_url = {a.game_url: a for a in analyses}

    wins = sum(1 for g in games if g.player_result(username) == "win")
    losses = sum(1 for g in games if g.player_result(username) == "loss")
    draws = sum(1 for g in games if g.player_result(username) == "draw")

    game_cards = []
    all_mistakes = []

    for i, game in enumerate(games, 1):
        color = game.player_color(username)
        result = game.player_result(username)
        opponent = game.opponent_username(username)
        result_class = {"win": "success", "loss": "danger", "draw": ""}[result]
        result_label = {"win": "WIN", "loss": "LOSS", "draw": "DRAW"}[result]

        acc_html = ""
        acc = game.player_accuracy(username)
        if acc is not None:
            acc_html = f"<span class='acc'>Accuracy: {acc:.1f}%</span>"

        mistake_html = ""
        analysis = analysis_by_url.get(game.url)
        if analysis:
            mistake = get_key_mistake(analysis, color)
            if mistake:
                all_mistakes.append(mistake)
                best = f"Best: {mistake.best_move_san}" if mistake.best_move_san else ""
                btype = mistake.blunder_type.replace("_", " ").title() if mistake.blunder_type else ""

                board_html = ""
                if mistake.fen:
                    board = chess.Board(mistake.fen)
                    board_html = chess.svg.board(board, size=200,
                                                 flipped=color == "black",
                                                 coordinates=True)

                mistake_html = f"""
                <div class="mistake">
                    <div class="mistake-text">
                        <p class="mistake-label">Key Mistake</p>
                        <p>Move {mistake.move_number}: <strong>{mistake.move_san}</strong>
                        <span class="cp-loss">-{mistake.cp_loss}cp</span></p>
                        <p class="mistake-detail">{btype} · {best}</p>
                    </div>
                    <div class="mistake-board">{board_html}</div>
                </div>
                """
            else:
                mistake_html = '<p class="clean-game">Clean game — no major mistakes!</p>'

        game_cards.append(f"""
        <div class="game-card {result_class}">
            <div class="game-header">
                <span class="game-num">Game {i}</span>
                <span class="result-badge {result_class}">{result_label}</span>
            </div>
            <p>vs <strong>{opponent}</strong> · {game.time_class} · {color}</p>
            <p class="opening">{game.opening or 'Unknown opening'}</p>
            {acc_html}
            {mistake_html}
            <a href="{game.url}" target="_blank" class="game-link">View on Chess.com</a>
        </div>
        """)

    # Pattern summary
    pattern_html = ""
    if all_mistakes:
        avg_loss = sum(m.cp_loss for m in all_mistakes) / len(all_mistakes)
        blunder_count = sum(1 for m in all_mistakes if m.category == "blunder")

        if avg_loss > 500:
            takeaway = "Big swings today. Focus on checking for hanging pieces before every move."
            takeaway_class = "danger"
        elif avg_loss > 200:
            takeaway = "Moderate mistakes. Slow down on critical moves — check captures and checks first."
            takeaway_class = ""
        else:
            takeaway = "Solid day. Your mistakes were minor — keep it up."
            takeaway_class = "success"

        pattern_html = f"""
        <div class="section {takeaway_class}" style="margin-top:1.5rem">
            <h2>Today's Pattern</h2>
            <p>Worst move avg: <strong>{avg_loss:.0f}cp loss</strong> · {blunder_count} blunders across {len(games)} games</p>
            <p style="margin-top:0.75rem;color:#e6edf3">{takeaway}</p>
        </div>
        """

    cards_html = "\n".join(game_cards)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Review: {date}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #0d1117; color: #e6edf3;
    padding: 2rem; max-width: 900px; margin: 0 auto;
}}
h1 {{ color: #58a6ff; text-align: center; margin-bottom: 0.5rem; }}
.subtitle {{ text-align: center; color: #8b949e; margin-bottom: 0.5rem; }}
.summary {{ text-align: center; margin-bottom: 2rem; font-size: 1.2rem; }}
.game-card {{
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 1.5rem; margin-bottom: 1.5rem;
}}
.game-card.success {{ border-color: #23863644; }}
.game-card.danger {{ border-color: #f8514944; }}
.game-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }}
.game-num {{ font-weight: bold; color: #58a6ff; }}
.result-badge {{
    padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.8rem; font-weight: bold;
}}
.result-badge.success {{ background: #23863633; color: #3fb950; }}
.result-badge.danger {{ background: #f8514933; color: #f85149; }}
.opening {{ color: #8b949e; font-size: 0.9rem; margin: 0.25rem 0; }}
.acc {{ color: #8b949e; font-size: 0.85rem; }}
.mistake {{
    display: flex; gap: 1rem; margin-top: 1rem; padding-top: 1rem;
    border-top: 1px solid #30363d; align-items: center; flex-wrap: wrap;
}}
.mistake-label {{ color: #f85149; font-weight: bold; font-size: 0.85rem; margin-bottom: 0.25rem; }}
.mistake-text {{ flex: 1; min-width: 200px; }}
.mistake-board svg {{ max-width: 200px; height: auto; }}
.mistake-detail {{ color: #8b949e; font-size: 0.85rem; }}
.cp-loss {{ color: #f85149; font-weight: bold; }}
.clean-game {{ color: #3fb950; margin-top: 0.75rem; }}
.game-link {{ color: #58a6ff; font-size: 0.8rem; text-decoration: none; display: block; margin-top: 0.75rem; }}
.section {{
    background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem;
}}
.section.danger {{ border-color: #f8514944; }}
.section.success {{ border-color: #23863644; }}
h2 {{ font-size: 1.1rem; color: #58a6ff; margin-bottom: 0.75rem; }}
footer {{ text-align: center; color: #484f58; margin-top: 2rem; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>Daily Review</h1>
<p class="subtitle">{date}</p>
<p class="summary">{wins}W / {losses}L / {draws}D</p>
{cards_html}
{pattern_html}
<footer>Generated by chess-profiler · {now}</footer>
</body>
</html>"""


def save_review(games: list[Game], analyses: list[GameAnalysis],
                username: str, date: str, fmt: str = "html") -> Path:
    """Save a daily review to reports/."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_clean = date.replace(".", "-")

    if fmt == "html":
        path = REPORT_DIR / f"{username}_review_{date_clean}.html"
        path.write_text(generate_review_html(games, analyses, username, date))
    else:
        path = REPORT_DIR / f"{username}_review_{date_clean}.txt"
        path.write_text(generate_review(games, analyses, username, date))

    return path
