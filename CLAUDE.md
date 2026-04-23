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
```

## Architecture

Pipeline: **API fetch → Game model → Profiler → CLI output**

- `src/api.py` — Chess.com API client. Fetches monthly game archives as raw JSON dicts.
- `src/models.py` — `Game` dataclass and `game_from_api()` parser. Extracts opening names from Chess.com's ECO URLs. All player-relative queries (result, color, rating, accuracy) go through `Game` methods.
- `src/profiler.py` — `build_profile()` aggregates games into a `Profile` with stats by color, time control, opening, loss type, game length, and accuracy trends. `format_profile()` renders the text report.
- `src/report.py` — `generate_html()` produces a self-contained dark-theme HTML report with CSS bar charts and SVG sparklines. `save_report()` writes to `reports/`.
- `src/cli.py` — Argparse entry point, wires the pipeline together. Flags: `-n` months, `-f` format, `-o` save.

## Chess.com API

No auth required. Set `User-Agent` header to avoid blocks. Key endpoints:
- Archives list: `GET /pub/player/{username}/games/archives` → `{"archives": [url, ...]}`
- Monthly games: `GET /pub/player/{username}/games/{YYYY}/{MM}` → `{"games": [...]}`

Game objects include: `white`/`black` (username, rating, result), `time_class`, `time_control`, `accuracies`, `eco` (opening URL), `pgn`, `fen`.

## Environment

- `.venv/` — virtual environment (gitignored)
- `.env` — secrets (gitignored)
- `data/raw/`, `data/processed/` — cached game data (gitignored)
