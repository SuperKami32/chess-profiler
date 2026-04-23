"""Opponent prep — analyze an opponent's games to prepare for a match."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .api import get_all_games
from .models import Game, game_from_api
from .profiler import Stats

REPORT_DIR = Path(__file__).parent.parent / "reports"


def build_opponent_profile(opponent: str, last_n_months: int | None = 6) -> dict:
    """Fetch and analyze an opponent's games."""
    print(f"  Fetching {opponent}'s games...")
    raw = get_all_games(opponent, last_n_months=last_n_months)
    games = [game_from_api(g) for g in raw]

    if not games:
        return {"username": opponent, "games": 0}

    overall = Stats()
    as_white = Stats()
    as_black = Stats()
    openings_as_white = defaultdict(Stats)
    openings_as_black = defaultdict(Stats)
    time_classes = defaultdict(Stats)
    ratings = []
    accuracies = []

    for game in games:
        result = game.player_result(opponent)
        if result is None:
            continue

        color = game.player_color(opponent)
        overall.record(result)

        if color == "white":
            as_white.record(result)
            if game.opening:
                openings_as_white[game.opening].record(result)
        else:
            as_black.record(result)
            if game.opening:
                openings_as_black[game.opening].record(result)

        time_classes[game.time_class].record(result)

        rating = game.player_rating(opponent)
        if rating:
            ratings.append(rating)

        acc = game.player_accuracy(opponent)
        if acc:
            accuracies.append(acc)

    return {
        "username": opponent,
        "games": len(games),
        "overall": overall,
        "as_white": as_white,
        "as_black": as_black,
        "openings_as_white": dict(openings_as_white),
        "openings_as_black": dict(openings_as_black),
        "time_classes": dict(time_classes),
        "current_rating": ratings[-1] if ratings else None,
        "avg_accuracy": sum(accuracies) / len(accuracies) if accuracies else None,
    }


def generate_prep(opponent_profile: dict, your_username: str,
                  your_games: list[Game] = None) -> str:
    """Generate a text prep report for an opponent."""
    opp = opponent_profile
    username = opp["username"]

    if opp["games"] == 0:
        return f"No games found for {username}."

    lines = []
    lines.append(f"=== Opponent Prep: {username} ===")
    lines.append(f"Games analyzed: {opp['games']}")
    if opp["current_rating"]:
        lines.append(f"Current rating: {opp['current_rating']}")
    if opp["avg_accuracy"]:
        lines.append(f"Average accuracy: {opp['avg_accuracy']:.1f}%")
    lines.append(f"Overall: {opp['overall']}")
    lines.append("")

    # Their performance by color
    lines.append("--- Their Performance ---")
    lines.append(f"  As white: {opp['as_white']}")
    lines.append(f"  As black: {opp['as_black']}")
    weaker_color = "white" if opp["as_white"].win_rate < opp["as_black"].win_rate else "black"
    lines.append(f"  → They're weaker as {weaker_color}")
    lines.append("")

    # What they play as white (you'll face this as black)
    if opp["openings_as_white"]:
        lines.append("--- What They Play as White (prepare as black) ---")
        sorted_openings = sorted(opp["openings_as_white"].items(),
                                 key=lambda x: x[1].total, reverse=True)
        for name, stats in sorted_openings[:8]:
            lines.append(f"  {name}: {stats}")
        lines.append("")

    # What they play as black (you'll face this as white)
    if opp["openings_as_black"]:
        lines.append("--- What They Play as Black (prepare as white) ---")
        sorted_openings = sorted(opp["openings_as_black"].items(),
                                 key=lambda x: x[1].total, reverse=True)
        for name, stats in sorted_openings[:8]:
            lines.append(f"  {name}: {stats}")
        lines.append("")

    # Their weakest openings
    all_openings = {}
    for name, stats in opp["openings_as_white"].items():
        if stats.total >= 2:
            all_openings[f"{name} (as white)"] = stats
    for name, stats in opp["openings_as_black"].items():
        if stats.total >= 2:
            all_openings[f"{name} (as black)"] = stats

    if all_openings:
        worst = sorted(all_openings.items(), key=lambda x: x[1].win_rate)[:5]
        lines.append("--- Their Weakest Openings ---")
        for name, stats in worst:
            lines.append(f"  {name}: {stats}")
        lines.append("")

    # Prep recommendations
    lines.append("--- Prep Recommendations ---")

    # What to play as white against them
    if opp["openings_as_black"]:
        worst_black = sorted(opp["openings_as_black"].items(),
                             key=lambda x: x[1].win_rate)
        if worst_black:
            name, stats = worst_black[0]
            if stats.win_rate < 0.5 and stats.total >= 2:
                lines.append(f"  As WHITE: Try to steer into the {name}")
                lines.append(f"    They're {stats.wins}W/{stats.losses}L here")

    # What to play as black against them
    if opp["openings_as_white"]:
        # Find their most played white opening — you need to be ready for it
        most_played = sorted(opp["openings_as_white"].items(),
                             key=lambda x: x[1].total, reverse=True)
        if most_played:
            name, stats = most_played[0]
            lines.append(f"  As BLACK: Expect the {name} ({stats.total} games)")
            lines.append(f"    Study your responses to this opening")

    # Time control recommendation
    if opp["time_classes"]:
        worst_tc = min(opp["time_classes"].items(), key=lambda x: x[1].win_rate)
        if worst_tc[1].total >= 3:
            lines.append(f"  Time control: They're weakest at {worst_tc[0]} "
                         f"({worst_tc[1].win_rate*100:.0f}% win rate)")

    # Compare accuracy if we have the user's data
    if your_games and opp["avg_accuracy"]:
        your_accs = [g.player_accuracy(your_username) for g in your_games
                     if g.player_accuracy(your_username) is not None]
        if your_accs:
            your_avg = sum(your_accs) / len(your_accs)
            diff = your_avg - opp["avg_accuracy"]
            if diff > 3:
                lines.append(f"  Accuracy edge: You ({your_avg:.1f}%) vs them ({opp['avg_accuracy']:.1f}%) — "
                             f"you're more accurate, play solid and let them make mistakes")
            elif diff < -3:
                lines.append(f"  Accuracy edge: They ({opp['avg_accuracy']:.1f}%) vs you ({your_avg:.1f}%) — "
                             f"they're more accurate, look for tactical complications")

    return "\n".join(lines)


def generate_prep_html(opponent_profile: dict, your_username: str,
                       your_games: list[Game] = None) -> str:
    """Generate an HTML prep report."""
    opp = opponent_profile
    username = opp["username"]

    if opp["games"] == 0:
        return f"<html><body><h1>No games found for {username}</h1></body></html>"

    sections = []

    # Header
    weaker_color = "white" if opp["as_white"].win_rate < opp["as_black"].win_rate else "black"
    sections.append(f"""
    <h1>Opponent Prep: {username}</h1>
    <div class="cards">
        <div class="card"><div class="card-value">{opp['games']}</div><div class="card-label">Games</div></div>
        <div class="card"><div class="card-value">{opp['current_rating'] or '?'}</div><div class="card-label">Rating</div></div>
        <div class="card"><div class="card-value">{opp['overall'].win_rate*100:.0f}%</div><div class="card-label">Win Rate</div></div>
        <div class="card"><div class="card-value">{opp['avg_accuracy']:.1f}%</div><div class="card-label">Avg Accuracy</div></div>
        <div class="card" style="border-color:#f85149"><div class="card-value">{weaker_color}</div><div class="card-label">Weaker As</div></div>
    </div>
    """)

    # What they play as white
    if opp["openings_as_white"]:
        rows = ""
        for name, stats in sorted(opp["openings_as_white"].items(), key=lambda x: x[1].total, reverse=True)[:8]:
            rows += f"<tr><td>{name}</td><td>{stats.total}</td><td>{stats.win_rate*100:.0f}%</td></tr>"
        sections.append(f"""
        <div class="section">
            <h2>What They Play as White (prepare as black)</h2>
            <table><tr><th>Opening</th><th>Games</th><th>Their Win%</th></tr>{rows}</table>
        </div>
        """)

    # What they play as black
    if opp["openings_as_black"]:
        rows = ""
        for name, stats in sorted(opp["openings_as_black"].items(), key=lambda x: x[1].total, reverse=True)[:8]:
            rows += f"<tr><td>{name}</td><td>{stats.total}</td><td>{stats.win_rate*100:.0f}%</td></tr>"
        sections.append(f"""
        <div class="section">
            <h2>What They Play as Black (prepare as white)</h2>
            <table><tr><th>Opening</th><th>Games</th><th>Their Win%</th></tr>{rows}</table>
        </div>
        """)

    # Their weakest openings
    all_openings = {}
    for name, stats in opp["openings_as_white"].items():
        if stats.total >= 2:
            all_openings[f"{name} (white)"] = stats
    for name, stats in opp["openings_as_black"].items():
        if stats.total >= 2:
            all_openings[f"{name} (black)"] = stats
    if all_openings:
        rows = ""
        for name, stats in sorted(all_openings.items(), key=lambda x: x[1].win_rate)[:5]:
            rows += f"<tr><td>{name}</td><td>{stats.total}</td><td>{stats.win_rate*100:.0f}%</td></tr>"
        sections.append(f"""
        <div class="section danger">
            <h2>Their Weakest Openings — Exploit These</h2>
            <table><tr><th>Opening</th><th>Games</th><th>Their Win%</th></tr>{rows}</table>
        </div>
        """)

    body = "\n".join(sections)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Opponent Prep: {username}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #0d1117; color: #e6edf3; padding: 2rem; max-width: 900px; margin: 0 auto;
}}
h1 {{ color: #58a6ff; text-align: center; margin-bottom: 1.5rem; }}
.cards {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap: 1rem; margin-bottom: 2rem;
}}
.card {{
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 1rem; text-align: center;
}}
.card-value {{ font-size: 1.3rem; font-weight: bold; }}
.card-label {{ font-size: 0.8rem; color: #8b949e; margin-top: 0.25rem; }}
.section {{
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 1.5rem; margin-bottom: 1.5rem;
}}
.section.danger {{ border-color: #f8514944; }}
h2 {{ font-size: 1.1rem; color: #58a6ff; margin-bottom: 1rem; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; color: #8b949e; font-weight: normal; font-size: 0.85rem; padding: 0.5rem; border-bottom: 1px solid #30363d; }}
td {{ padding: 0.5rem; border-bottom: 1px solid #21262d; }}
footer {{ text-align: center; color: #484f58; margin-top: 2rem; font-size: 0.8rem; }}
</style>
</head>
<body>
{body}
<footer>Generated by chess-profiler · {now}</footer>
</body>
</html>"""


def save_prep(opponent_profile: dict, your_username: str,
              your_games: list[Game] = None, fmt: str = "html") -> Path:
    """Save prep report to reports/."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    opp_name = opponent_profile["username"]

    if fmt == "html":
        path = REPORT_DIR / f"prep_{opp_name}.html"
        path.write_text(generate_prep_html(opponent_profile, your_username, your_games))
    else:
        path = REPORT_DIR / f"prep_{opp_name}.txt"
        path.write_text(generate_prep(opponent_profile, your_username, your_games))

    return path
