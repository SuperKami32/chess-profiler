"""Command-line interface for chess-profiler."""

import argparse
import sys
from datetime import datetime, timedelta

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
    parser.add_argument(
        "--puzzles", action="store_true",
        help="Generate tactic puzzles from blunders (implies --analyze)",
    )
    parser.add_argument(
        "--review", nargs="?", const="yesterday", metavar="DATE",
        help="Daily review mode. Optionally pass a date (YYYY.MM.DD). Defaults to yesterday.",
    )
    parser.add_argument(
        "--prep", metavar="OPPONENT",
        help="Generate opponent prep report for OPPONENT username",
    )
    args = parser.parse_args()

    # --puzzles implies --analyze
    if args.puzzles:
        args.analyze = True

    # --review implies --analyze
    if args.review:
        args.analyze = True

    username = args.username

    # --- Opponent prep mode ---
    if args.prep:
        from .prep import build_opponent_profile, generate_prep, save_prep

        # Fetch user's games for comparison
        print(f"Fetching {username}'s games for comparison...")
        raw = get_all_games(username, last_n_months=args.months)
        your_games = [game_from_api(g) for g in raw]

        opp = build_opponent_profile(args.prep, last_n_months=args.months or 6)

        if args.format == "html" or args.output:
            path = save_prep(opp, username, your_games, fmt=args.format)
            print(f"\nPrep report saved to: {path}")
        else:
            print()
            print(generate_prep(opp, username, your_games))
        return

    # --- Fetch games ---
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

    # --- Daily review mode ---
    if args.review:
        from .review import filter_games_by_date, generate_review, save_review
        from .engine import analyze_games

        if args.review == "yesterday":
            date = (datetime.now() - timedelta(days=1)).strftime("%Y.%m.%d")
        else:
            date = args.review

        day_games = filter_games_by_date(games, date)
        if not day_games:
            print(f"No games found for {date}.")
            # Show nearby dates with games
            from collections import Counter
            date_counts = Counter(g.date for g in games)
            recent = sorted(date_counts.items(), reverse=True)[:5]
            if recent:
                print("Recent dates with games:")
                for d, c in recent:
                    print(f"  {d}: {c} games")
            sys.exit(0)

        def progress(current, total, cached=False):
            status = "cached" if cached else "analyzing"
            print(f"\r  Engine analysis: {current}/{total} ({status})...", end="", flush=True)

        print(f"Found {len(day_games)} games on {date}. Running analysis...")
        analyses = analyze_games(day_games, depth=args.depth, progress_callback=progress)
        print()

        if args.format == "html" or args.output:
            path = save_review(day_games, analyses, username, date, fmt=args.format)
            print(f"Review saved to: {path}")
        else:
            print(generate_review(day_games, analyses, username, date))
        return

    # --- Standard profile mode ---
    profile = build_profile(username, games)

    analyses = None
    if args.analyze:
        from .engine import analyze_games

        def progress(current, total, cached=False):
            status = "cached" if cached else "analyzing"
            print(f"\r  Engine analysis: {current}/{total} ({status})...", end="", flush=True)

        print("Running Stockfish analysis...")
        analyses = analyze_games(games, depth=args.depth, progress_callback=progress)
        print()  # newline after progress
        enrich_with_analysis(profile, analyses, games)

    # Pattern recognition and opening recommendations (always included)
    from .patterns import analyze_patterns, format_patterns
    from .openings import analyze_openings, format_recommendations

    opening_recs = analyze_openings(profile, games)

    if args.puzzles and analyses:
        from .puzzles import extract_puzzles, save_puzzles
        puzzles = extract_puzzles(analyses, username, games)
        path = save_puzzles(puzzles, username)
        print(f"Generated {len(puzzles)} puzzles → {path}")

    if args.output or args.format == "html":
        pattern_report = analyze_patterns(analyses, username, games) if analyses else None
        path = save_report(profile, fmt=args.format,
                           pattern_report=pattern_report,
                           opening_recs=opening_recs)
        print(f"\nReport saved to: {path}")
    else:
        print()
        print(format_profile(profile))
        if analyses:
            pattern_report = analyze_patterns(analyses, username, games)
            print()
            print(format_patterns(pattern_report))
        print()
        print(format_recommendations(opening_recs))


if __name__ == "__main__":
    main()
