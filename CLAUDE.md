# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chess Profiler pulls game data from the Chess.com public API and generates weakness analysis. Target username: `superkami32`.

## Commands

```bash
# Setup
python3 -m venv .venv && .venv/bin/pip install -e .

# Run
.venv/bin/python -m src.cli <username>              # text report to stdout
.venv/bin/python -m src.cli <username> -n 6          # last 6 months only
.venv/bin/python -m src.cli <username> -f html       # HTML report to reports/
.venv/bin/python -m src.cli <username> -o             # save text report to reports/
.venv/bin/python -m src.cli <username> --analyze      # run Stockfish blunder detection
.venv/bin/python -m src.cli <username> --analyze --depth 16  # deeper analysis (slower)
.venv/bin/python -m src.cli <username> --puzzles             # generate tactic puzzle HTML (implies --analyze)
```

## Architecture

Pipeline: **API fetch → Game model → Profiler → CLI output**

- `src/api.py` — Chess.com API client. Fetches monthly game archives as raw JSON dicts.
- `src/models.py` — `Game` dataclass and `game_from_api()` parser. Extracts opening names from Chess.com's ECO URLs. All player-relative queries (result, color, rating, accuracy) go through `Game` methods.
- `src/profiler.py` — `build_profile()` aggregates games into a `Profile` with stats by color, time control, opening, loss type, game length, and accuracy trends. `format_profile()` renders the text report.
- `src/report.py` — `generate_html()` produces a self-contained dark-theme HTML report with CSS bar charts and SVG sparklines. `save_report()` writes to `reports/`.
- `src/engine.py` — Stockfish integration via `python-chess`. `analyze_game()` walks PGN move-by-move, computes centipawn loss, classifies blunders (hung piece, missed tactic, missed mate, bad trade). Results cached as JSON in `data/processed/`. `analyze_games()` handles batch analysis with caching.
- `src/puzzles.py` — Extracts blunder positions as interactive HTML puzzles with SVG boards (via `chess.svg`). Click to reveal the best move.
- `src/patterns.py` — Blunder pattern recognition: which pieces you blunder with, tactical motifs missed (captures, checks, forks, discovered attacks), board region, eval context (blundering when winning/even/losing). Generates natural-language insights.
- `src/openings.py` — Opening recommendations: identifies problem openings (high frequency, low win rate) and strengths. Generates specific study suggestions.
- `src/cli.py` — Argparse entry point, wires the pipeline together. Flags: `-n` months, `-f` format, `-o` save, `--analyze`, `--depth`, `--puzzles`.

## Chess.com API

No auth required. Set `User-Agent` header to avoid blocks. Key endpoints:
- Archives list: `GET /pub/player/{username}/games/archives` → `{"archives": [url, ...]}`
- Monthly games: `GET /pub/player/{username}/games/{YYYY}/{MM}` → `{"games": [...]}`

Game objects include: `white`/`black` (username, rating, result), `time_class`, `time_control`, `accuracies`, `eco` (opening URL), `pgn`, `fen`.

## Environment

- `.venv/` — virtual environment (gitignored)
- `.env` — secrets (gitignored)
- `data/raw/`, `data/processed/` — cached game data (gitignored)
- Stockfish binary at `/usr/games/stockfish` (system-installed)
