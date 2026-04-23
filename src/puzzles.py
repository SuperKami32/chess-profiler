"""Generate tactic puzzles from blunder positions."""

from datetime import datetime
from pathlib import Path

import chess
import chess.svg

from .engine import GameAnalysis, MoveAnalysis

REPORT_DIR = Path(__file__).parent.parent / "reports"


def _board_svg(fen: str, best_move_san: str | None = None, size: int = 320) -> str:
    """Render a chess board as SVG, optionally highlighting the best move."""
    board = chess.Board(fen)

    arrows = []
    if best_move_san:
        move = board.parse_san(best_move_san)
        arrows = [chess.svg.Arrow(move.from_square, move.to_square, color="#22c55e")]

    return chess.svg.board(
        board,
        size=size,
        arrows=arrows,
        coordinates=True,
        flipped=board.turn == chess.BLACK,
    )


def extract_puzzles(analyses: list[GameAnalysis], username: str,
                    games: list = None, min_cp_loss: int = 200) -> list[dict]:
    """Extract puzzle positions from analyzed games.

    Returns list of puzzle dicts with fen, best_move, played_move, cp_loss, etc.
    """
    from .models import Game

    game_by_url = {}
    if games:
        for g in games:
            if isinstance(g, Game):
                game_by_url[g.url] = g

    puzzles = []
    for analysis in analyses:
        game = game_by_url.get(analysis.game_url)
        if not game:
            continue

        color = game.player_color(username)
        if not color:
            continue

        for move in analysis.moves:
            if move.color != color:
                continue
            if move.cp_loss < min_cp_loss:
                continue
            if not move.fen or not move.best_move_san:
                continue

            puzzles.append({
                "fen": move.fen,
                "best_move": move.best_move_san,
                "played_move": move.move_san,
                "cp_loss": move.cp_loss,
                "move_number": move.move_number,
                "blunder_type": move.blunder_type or "other",
                "game_url": analysis.game_url,
                "opening": game.opening or "Unknown",
                "color": color,
            })

    # Sort by cp_loss descending — worst blunders first
    puzzles.sort(key=lambda p: p["cp_loss"], reverse=True)
    return puzzles


def generate_puzzle_html(puzzles: list[dict], username: str) -> str:
    """Generate an interactive HTML puzzle page."""
    if not puzzles:
        return "<html><body><h1>No puzzles to show</h1></body></html>"

    puzzle_cards = []
    for i, p in enumerate(puzzles):
        board_svg = _board_svg(p["fen"])
        board_svg_answer = _board_svg(p["fen"], p["best_move"])
        btype = p["blunder_type"].replace("_", " ").title()

        # Determine whose turn it is from FEN
        turn = "White" if " w " in p["fen"] else "Black"

        puzzle_cards.append(f"""
        <div class="puzzle" id="puzzle-{i}">
            <div class="puzzle-header">
                <span class="puzzle-num">#{i+1}</span>
                <span class="puzzle-meta">{turn} to move · Move {p['move_number']} · {btype}</span>
                <span class="puzzle-loss">-{p['cp_loss']}cp</span>
            </div>
            <div class="board-container">
                <div class="board question" id="board-q-{i}">{board_svg}</div>
                <div class="board answer" id="board-a-{i}" style="display:none">{board_svg_answer}</div>
            </div>
            <div class="puzzle-info">
                <p class="you-played">You played: <strong>{p['played_move']}</strong></p>
                <div class="answer-section" id="answer-{i}" style="display:none">
                    <p class="best-move">Best move: <strong>{p['best_move']}</strong></p>
                </div>
                <button onclick="reveal({i})" id="btn-{i}">Show Answer</button>
                <p class="opening">{p['opening']}</p>
                <a href="{p['game_url']}" target="_blank" class="game-link">View full game</a>
            </div>
        </div>
        """)

    cards_html = "\n".join(puzzle_cards)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tactic Puzzles: {username}</title>
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
h1 {{ color: #58a6ff; text-align: center; margin-bottom: 0.5rem; font-size: 1.8rem; }}
.subtitle {{ text-align: center; color: #8b949e; margin-bottom: 2rem; }}
.stats {{
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin-bottom: 2rem;
    flex-wrap: wrap;
}}
.stat {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.75rem 1.5rem;
    text-align: center;
}}
.stat-value {{ font-size: 1.3rem; font-weight: bold; }}
.stat-label {{ font-size: 0.8rem; color: #8b949e; }}
.puzzle {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}}
.puzzle-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    flex-wrap: wrap;
    gap: 0.5rem;
}}
.puzzle-num {{ font-weight: bold; color: #58a6ff; font-size: 1.1rem; }}
.puzzle-meta {{ color: #8b949e; font-size: 0.9rem; }}
.puzzle-loss {{ color: #f85149; font-weight: bold; }}
.board-container {{ display: flex; justify-content: center; margin-bottom: 1rem; }}
.board svg {{ max-width: 100%; height: auto; }}
.puzzle-info {{ text-align: center; }}
.you-played {{ color: #f85149; margin-bottom: 0.5rem; }}
.best-move {{ color: #22c55e; margin-bottom: 0.5rem; font-size: 1.1rem; }}
button {{
    background: #238636;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 0.5rem 1.5rem;
    cursor: pointer;
    font-size: 0.95rem;
    margin: 0.5rem 0;
}}
button:hover {{ background: #2ea043; }}
button.revealed {{ background: #30363d; cursor: default; }}
.opening {{ color: #8b949e; font-size: 0.8rem; margin-top: 0.5rem; }}
.game-link {{ color: #58a6ff; font-size: 0.8rem; text-decoration: none; }}
.game-link:hover {{ text-decoration: underline; }}
footer {{ text-align: center; color: #484f58; margin-top: 2rem; font-size: 0.8rem; }}
</style>
<script>
function reveal(i) {{
    document.getElementById('answer-' + i).style.display = 'block';
    document.getElementById('board-q-' + i).style.display = 'none';
    document.getElementById('board-a-' + i).style.display = 'block';
    var btn = document.getElementById('btn-' + i);
    btn.textContent = 'Revealed';
    btn.className = 'revealed';
    btn.onclick = null;
}}
</script>
</head>
<body>
<h1>♟ Tactic Puzzles</h1>
<p class="subtitle">Positions from your games where you missed the best move</p>

<div class="stats">
    <div class="stat">
        <div class="stat-value">{len(puzzles)}</div>
        <div class="stat-label">Puzzles</div>
    </div>
    <div class="stat">
        <div class="stat-value">{sum(1 for p in puzzles if p['blunder_type'] == 'missed_tactic')}</div>
        <div class="stat-label">Missed Tactics</div>
    </div>
    <div class="stat">
        <div class="stat-value">{sum(1 for p in puzzles if p['blunder_type'] == 'hung_piece')}</div>
        <div class="stat-label">Hung Pieces</div>
    </div>
    <div class="stat">
        <div class="stat-value">{sum(1 for p in puzzles if p['blunder_type'] == 'missed_mate')}</div>
        <div class="stat-label">Missed Mates</div>
    </div>
</div>

{cards_html}

<footer>Generated by chess-profiler · {now}</footer>
</body>
</html>"""


def save_puzzles(puzzles: list[dict], username: str) -> Path:
    """Save puzzle HTML to reports/ directory."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{username}_puzzles_{timestamp}.html"
    path.write_text(generate_puzzle_html(puzzles, username))
    return path
