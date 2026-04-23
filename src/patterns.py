"""Blunder pattern recognition — find recurring weaknesses across games."""

from collections import defaultdict
from dataclasses import dataclass, field

import chess

from .engine import GameAnalysis, MoveAnalysis


PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


@dataclass
class PatternReport:
    """Aggregated blunder patterns across games."""
    total_blunders: int = 0

    # Which piece was moved when blundering
    piece_moved: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # What piece the best move would have captured/used (tactical motifs)
    missed_capture_piece: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Board region where blunders happen
    # kingside (files f-h), center (files d-e), queenside (files a-c)
    region: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Whether blunder happened when ahead, behind, or even
    eval_context: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Tactical motifs detected in the best move
    motifs: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def _square_region(square: int) -> str:
    file = chess.square_file(square)
    if file <= 2:
        return "queenside"
    elif file >= 5:
        return "kingside"
    return "center"


def _detect_motif(board: chess.Board, best_move: chess.Move) -> list[str]:
    """Detect tactical motifs in the best move."""
    motifs = []

    # Check if best move is a check
    board_after = board.copy()
    board_after.push(best_move)
    if board_after.is_check():
        motifs.append("check")
    if board_after.is_checkmate():
        motifs.append("checkmate")

    # Check if best move is a capture
    if board.is_capture(best_move):
        captured_sq = best_move.to_square
        captured_piece = board.piece_at(captured_sq)
        # En passant
        if captured_piece is None and board.piece_at(best_move.from_square).piece_type == chess.PAWN:
            motifs.append("capture")
        elif captured_piece:
            motifs.append("capture")

    # Check for fork — after the move, does the piece attack 2+ valuable pieces?
    if not board_after.is_checkmate():
        moved_piece = board_after.piece_at(best_move.to_square)
        if moved_piece:
            attacked_valuable = 0
            for sq in chess.SQUARES:
                target = board_after.piece_at(sq)
                if target and target.color != moved_piece.color:
                    if board_after.is_attacked_by(moved_piece.color, sq):
                        if target.piece_type in (chess.ROOK, chess.QUEEN, chess.KING):
                            attacked_valuable += 1
            if attacked_valuable >= 2:
                motifs.append("fork")

    # Check for discovered attack — did moving the piece reveal an attack?
    moving_piece_type = board.piece_at(best_move.from_square).piece_type if board.piece_at(best_move.from_square) else None
    if moving_piece_type and not board.is_capture(best_move):
        # Check if a different piece now attacks something valuable
        for sq in chess.SQUARES:
            target = board_after.piece_at(sq)
            if target and target.color != board.turn:
                if target.piece_type in (chess.QUEEN, chess.KING):
                    # Was this square attacked before?
                    was_attacked = board.is_attacked_by(board.turn, sq)
                    is_attacked = board_after.is_attacked_by(board.turn, sq)
                    if is_attacked and not was_attacked:
                        motifs.append("discovered attack")
                        break

    # Promotion
    if best_move.promotion:
        motifs.append("promotion")

    if not motifs:
        motifs.append("positional")

    return motifs


def analyze_patterns(analyses: list[GameAnalysis], username: str,
                     games: list = None) -> PatternReport:
    """Analyze blunder patterns across multiple games."""
    from .models import Game

    game_by_url = {}
    if games:
        for g in games:
            if isinstance(g, Game):
                game_by_url[g.url] = g

    report = PatternReport()

    for analysis in analyses:
        game = game_by_url.get(analysis.game_url)
        if not game:
            continue

        color = game.player_color(username)
        if not color:
            continue

        for move in analysis.moves:
            if move.color != color or move.category != "blunder":
                continue
            if not move.fen:
                continue

            report.total_blunders += 1
            board = chess.Board(move.fen)

            # What piece was moved
            played_move = board.parse_san(move.move_san)
            moved_piece = board.piece_at(played_move.from_square)
            if moved_piece:
                report.piece_moved[PIECE_NAMES[moved_piece.piece_type]] += 1

            # Board region of the move
            region = _square_region(played_move.to_square)
            report.region[region] += 1

            # Eval context — were we ahead, behind, or even?
            if color == "white":
                eval_val = move.eval_before
            else:
                eval_val = -move.eval_before
            if eval_val > 100:
                report.eval_context["winning"] += 1
            elif eval_val < -100:
                report.eval_context["losing"] += 1
            else:
                report.eval_context["even"] += 1

            # Analyze the best move for tactical motifs
            if move.best_move_san:
                try:
                    best_move = board.parse_san(move.best_move_san)
                    motifs = _detect_motif(board, best_move)
                    for motif in motifs:
                        report.motifs[motif] += 1

                    # What piece would the best move have captured?
                    if board.is_capture(best_move):
                        captured = board.piece_at(best_move.to_square)
                        if captured:
                            report.missed_capture_piece[PIECE_NAMES[captured.piece_type]] += 1
                except (ValueError, chess.IllegalMoveError):
                    pass

    return report


def format_patterns(report: PatternReport) -> str:
    """Format pattern report as text."""
    if report.total_blunders == 0:
        return "No blunders to analyze."

    lines = []
    lines.append(f"--- Blunder Pattern Analysis ({report.total_blunders} blunders) ---")
    lines.append("")

    # Piece most often moved when blundering
    if report.piece_moved:
        lines.append("  Piece moved when blundering:")
        total = sum(report.piece_moved.values())
        for piece, count in sorted(report.piece_moved.items(), key=lambda x: x[1], reverse=True):
            pct = count / total * 100
            bar = "█" * int(pct / 3)
            lines.append(f"    {piece:8s}: {count:3d} ({pct:.0f}%) {bar}")
        lines.append("")

    # Board region
    if report.region:
        lines.append("  Blunder region:")
        total = sum(report.region.values())
        for region in ["kingside", "center", "queenside"]:
            if region in report.region:
                count = report.region[region]
                pct = count / total * 100
                bar = "█" * int(pct / 3)
                lines.append(f"    {region:10s}: {count:3d} ({pct:.0f}%) {bar}")
        lines.append("")

    # Eval context
    if report.eval_context:
        lines.append("  Position when blundering:")
        total = sum(report.eval_context.values())
        for ctx in ["winning", "even", "losing"]:
            if ctx in report.eval_context:
                count = report.eval_context[ctx]
                pct = count / total * 100
                bar = "█" * int(pct / 3)
                lines.append(f"    {ctx:10s}: {count:3d} ({pct:.0f}%) {bar}")
        lines.append("")

    # Tactical motifs in the best move
    if report.motifs:
        lines.append("  What you're missing (best move was):")
        total = sum(report.motifs.values())
        for motif, count in sorted(report.motifs.items(), key=lambda x: x[1], reverse=True):
            pct = count / total * 100
            bar = "█" * int(pct / 3)
            lines.append(f"    {motif:18s}: {count:3d} ({pct:.0f}%) {bar}")
        lines.append("")

    # Missed captures
    if report.missed_capture_piece:
        lines.append("  Missed capturing:")
        total = sum(report.missed_capture_piece.values())
        for piece, count in sorted(report.missed_capture_piece.items(), key=lambda x: x[1], reverse=True):
            pct = count / total * 100
            lines.append(f"    {piece:8s}: {count:3d} ({pct:.0f}%)")
        lines.append("")

    # Generate natural-language insights
    insights = _generate_insights(report)
    if insights:
        lines.append("  Key Insights:")
        for insight in insights:
            lines.append(f"    → {insight}")

    return "\n".join(lines)


def _generate_insights(report: PatternReport) -> list[str]:
    """Generate natural-language insights from pattern data."""
    insights = []

    # Most blundered piece
    if report.piece_moved:
        worst_piece = max(report.piece_moved, key=report.piece_moved.get)
        pct = report.piece_moved[worst_piece] / report.total_blunders * 100
        if pct >= 30:
            insights.append(
                f"Your {worst_piece} is your most problematic piece — "
                f"{pct:.0f}% of blunders involve moving it."
            )

    # Eval context — blundering when winning
    if "winning" in report.eval_context:
        winning_pct = report.eval_context["winning"] / report.total_blunders * 100
        if winning_pct >= 40:
            insights.append(
                f"You blunder {winning_pct:.0f}% of the time when already winning. "
                f"Slow down in winning positions."
            )

    # Board region
    if report.region:
        worst_region = max(report.region, key=report.region.get)
        pct = report.region[worst_region] / report.total_blunders * 100
        if pct >= 45:
            insights.append(
                f"Most blunders happen on the {worst_region} ({pct:.0f}%). "
                f"Pay extra attention to that side of the board."
            )

    # Tactical motifs
    if "capture" in report.motifs:
        capture_pct = report.motifs["capture"] / sum(report.motifs.values()) * 100
        if capture_pct >= 30:
            insights.append(
                f"You're frequently missing captures ({capture_pct:.0f}% of best moves). "
                f"Before each move, check: can I take something?"
            )

    if "check" in report.motifs:
        check_count = report.motifs["check"]
        if check_count >= 5:
            insights.append(
                f"You missed {check_count} checks that were the best move. "
                f"Always look for checks first."
            )

    if "fork" in report.motifs:
        fork_count = report.motifs["fork"]
        if fork_count >= 3:
            insights.append(
                f"You missed {fork_count} forks. Practice recognizing double attacks."
            )

    return insights
