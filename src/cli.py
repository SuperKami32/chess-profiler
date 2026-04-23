"""Command-line interface for chess-profiler."""

import argparse
import sys

from .api import get_all_games
from .models import game_from_api
from .profiler import build_profile, format_profile, enrich_with_analysis
from .report import save_report


def main():
    parser = argparse.ArgumentParser(description="Chess.com weakness profiler")
    parser.add_argument("username", help="Chess.com username to analyze")
    parser.add_argument(
        "-n", "--months", type=int, default=None,
        help="Only analyze last N months (default: all)",
    )
    parser.add_argument(
        "-f", "--format", choices=["text", "html"], default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "-o", "--output", action="store_true",
        help="Save report to reports/ directory",
    )
    parser.add_argument(
        "--analyze", action="store_true",
        help="Run Stockfish engine analysis (slower, but finds blunders)",
    )
    parser.add_argument(
        "--depth", type=int, default=12,
        help="Stockfish analysis depth (default: 12)",
    )
    args = parser.parse_args()

    username = args.username
    print(f"Fetching games for {username}...")

    try:
        raw_games = get_all_games(username, last_n_months=args.months)
    except Exception as e:
        print(f"Error fetching games: {e}", file=sys.stderr)
        sys.exit(1)

    if not raw_games:
        print("No games found.")
        sys.exit(0)

    print(f"Found {len(raw_games)} games. Analyzing...")
    games = [game_from_api(g) for g in raw_games]
    profile = build_profile(username, games)

    if args.analyze:
        from .engine import analyze_games

        def progress(current, total, cached=False):
            status = "cached" if cached else "analyzing"
            print(f"\r  Engine analysis: {current}/{total} ({status})...", end="", flush=True)

        print("Running Stockfish analysis...")
        analyses = analyze_games(games, depth=args.depth, progress_callback=progress)
        print()  # newline after progress
        enrich_with_analysis(profile, analyses, games)

    if args.output or args.format == "html":
        path = save_report(profile, fmt=args.format)
        print(f"\nReport saved to: {path}")
    else:
        print()
        print(format_profile(profile))


if __name__ == "__main__":
    main()
