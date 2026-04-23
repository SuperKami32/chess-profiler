"""Stockfish engine analysis — move-by-move evaluation and blunder detection."""

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import io

STOCKFISH_PATH = "/usr/games/stockfish"
CACHE_DIR = Path(__file__).parent.parent / "data" / "processed"

# Centipawn loss thresholds
INACCURACY_THRESHOLD = 50   # ≥50cp loss
MISTAKE_THRESHOLD = 100     # ≥100cp loss
BLUNDER_THRESHOLD = 200     # ≥200cp loss


@dataclass
class MoveAnalysis:
    move_number: int
    color: str  # "white" or "black"
    move_san: str
    eval_before: int  # centipawns from white's perspective
    eval_after: int
    best_move_san: str | None
    cp_loss: int  # always positive, from the moving player's perspective
    category: str  # "good", "inaccuracy", "mistake", "blunder"
    blunder_type: str | None = None  # "hung_piece", "missed_tactic", "bad_trade", "missed_mate", "other"
    fen: str | None = None  # position before the move (for puzzle extraction later)


@dataclass
class GameAnalysis:
    game_url: str
    moves: list[MoveAnalysis]

    @property
    def blunders(self) -> list[MoveAnalysis]:
        return [m for m in self.moves if m.category == "blunder"]

    @property
    def mistakes(self) -> list[MoveAnalysis]:
        return [m for m in self.moves if m.category == "mistake"]

    @property
    def inaccuracies(self) -> list[MoveAnalysis]:
        return [m for m in self.moves if m.category == "inaccuracy"]

    def player_blunders(self, color: str) -> list[MoveAnalysis]:
        return [m for m in self.blunders if m.color == color]

    def player_mistakes(self, color: str) -> list[MoveAnalysis]:
        return [m for m in self.mistakes if m.color == color]

    def to_dict(self) -> dict:
        return {"game_url": self.game_url, "moves": [asdict(m) for m in self.moves]}

    @classmethod
    def from_dict(cls, data: dict) -> "GameAnalysis":
        moves = [MoveAnalysis(**m) for m in data["moves"]]
        return cls(game_url=data["game_url"], moves=moves)


def _score_to_cp(score: chess.engine.PovScore) -> int:
    """Convert a PovScore to centipawns from white's perspective.

    Mate scores are converted to large centipawn values.
    """
    white_score = score.white()
    cp = white_score.score(mate_score=10000)
    return cp


def _categorize_loss(cp_loss: int) -> str:
    if cp_loss >= BLUNDER_THRESHOLD:
        return "blunder"
    if cp_loss >= MISTAKE_THRESHOLD:
        return "mistake"
    if cp_loss >= INACCURACY_THRESHOLD:
        return "inaccuracy"
    return "good"


def _classify_blunder(board_before: chess.Board, move: chess.Move,
                      best_move: chess.Move | None, eval_before: int, eval_after: int,
                      color: str) -> str:
    """Classify what kind of blunder this is by examining the board state.

    Categories:
    - hung_piece: moved a piece to a square where it's captured, or left a piece undefended
    - missed_mate: there was a forced mate that was missed
    - bad_trade: made a trade that lost material (e.g. bishop for pawn)
    - missed_tactic: best move was a capture/check that was missed
    - other: positional blunders that don't fit the above
    """
    # Check for missed mate
    mate_score = 10000
    if color == "white":
        if eval_before >= mate_score - 50 and eval_after < mate_score - 50:
            return "missed_mate"
    else:
        if eval_before <= -(mate_score - 50) and eval_after > -(mate_score - 50):
            return "missed_mate"

    # Check if the piece we moved is immediately capturable
    board_after = board_before.copy()
    board_after.push(move)
    to_square = move.to_square
    if board_after.is_attacked_by(not board_before.turn, to_square):
        moved_piece = board_before.piece_at(move.from_square)
        # Check if the square was already defended or if it's a fair trade
        if moved_piece and moved_piece.piece_type != chess.PAWN:
            attackers = board_after.attackers(not board_before.turn, to_square)
            defenders = board_after.attackers(board_before.turn, to_square)
            if len(attackers) > len(defenders):
                return "hung_piece"

    # Check if the best move was a tactic (capture or check)
    if best_move:
        if board_before.is_capture(best_move):
            return "missed_tactic"
        board_test = board_before.copy()
        board_test.push(best_move)
        if board_test.is_check():
            return "missed_tactic"

    # Check for bad trades — we captured but lost material
    if board_before.is_capture(move):
        return "bad_trade"

    return "other"


def analyze_game(pgn_text: str, game_url: str, depth: int = 12) -> GameAnalysis | None:
    """Analyze a single game's PGN with Stockfish.

    Returns None if the PGN can't be parsed.
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return None

    board = game.board()
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    try:
        move_analyses = []

        # Get initial evaluation
        info = engine.analyse(board, chess.engine.Limit(depth=depth))
        prev_eval = _score_to_cp(info["score"])

        for node in game.mainline():
            move = node.move
            moving_color = "white" if board.turn == chess.WHITE else "black"
            move_number = board.fullmove_number
            move_san = board.san(move)
            fen_before = board.fen()

            # Make the move
            board.push(move)

            # Evaluate position after the move
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            current_eval = _score_to_cp(info["score"])

            # Compute centipawn loss from the moving player's perspective
            if moving_color == "white":
                cp_loss = max(0, prev_eval - current_eval)
            else:
                cp_loss = max(0, current_eval - prev_eval)

            # Get best move (from the position before this move)
            best_move_san = None
            best_move_uci = None
            if cp_loss >= INACCURACY_THRESHOLD:
                board.pop()
                best_info = engine.analyse(board, chess.engine.Limit(depth=depth))
                if "pv" in best_info and best_info["pv"]:
                    best_move_uci = best_info["pv"][0]
                    best_move_san = board.san(best_move_uci)
                board.push(move)

            # Classify blunder type
            blunder_type = None
            if cp_loss >= BLUNDER_THRESHOLD:
                board.pop()
                blunder_type = _classify_blunder(
                    board, move, best_move_uci, prev_eval, current_eval, moving_color
                )
                board.push(move)

            move_analyses.append(MoveAnalysis(
                move_number=move_number,
                color=moving_color,
                move_san=move_san,
                eval_before=prev_eval,
                eval_after=current_eval,
                best_move_san=best_move_san,
                cp_loss=cp_loss,
                category=_categorize_loss(cp_loss),
                blunder_type=blunder_type,
                fen=fen_before if cp_loss >= BLUNDER_THRESHOLD else None,
            ))

            prev_eval = current_eval

        return GameAnalysis(game_url=game_url, moves=move_analyses)

    finally:
        engine.quit()


def _cache_key(game_url: str) -> str:
    """Generate a cache filename from a game URL."""
    # URL like https://www.chess.com/game/live/122579599228
    game_id = game_url.rsplit("/", 1)[-1]
    return f"analysis_{game_id}.json"


def load_cached(game_url: str) -> GameAnalysis | None:
    """Load cached analysis for a game, if it exists."""
    path = CACHE_DIR / _cache_key(game_url)
    if path.exists():
        data = json.loads(path.read_text())
        return GameAnalysis.from_dict(data)
    return None


def save_cache(analysis: GameAnalysis):
    """Save analysis results to the cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / _cache_key(analysis.game_url)
    path.write_text(json.dumps(analysis.to_dict()))


def analyze_games(games: list[dict], depth: int = 12,
                  progress_callback=None) -> list[GameAnalysis]:
    """Analyze multiple games, using cache when available.

    games: list of (pgn_text, game_url) tuples or Game model objects.
    progress_callback: called with (current, total) after each game.
    """
    from .models import Game

    results = []
    total = len(games)

    for i, game in enumerate(games):
        if isinstance(game, Game):
            pgn = game.pgn
            url = game.url
        else:
            pgn, url = game

        # Check cache first
        cached = load_cached(url)
        if cached:
            results.append(cached)
            if progress_callback:
                progress_callback(i + 1, total, cached=True)
            continue

        # Analyze
        if pgn:
            analysis = analyze_game(pgn, url, depth=depth)
            if analysis:
                save_cache(analysis)
                results.append(analysis)

        if progress_callback:
            progress_callback(i + 1, total, cached=False)

    return results
