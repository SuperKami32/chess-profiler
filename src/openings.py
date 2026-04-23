"""Opening recommendations based on weakness data."""

from collections import defaultdict
from dataclasses import dataclass

from .models import Game
from .profiler import Profile, Stats


@dataclass
class OpeningRecommendation:
    name: str
    color: str
    games_played: int
    win_rate: float
    problem: str  # why this is recommended
    suggestion: str  # what to do about it


def analyze_openings(profile: Profile, games: list[Game]) -> list[OpeningRecommendation]:
    """Generate opening recommendations from profile data."""
    username = profile.username
    recommendations = []

    # 1. Find openings you face frequently but lose
    problem_openings = []
    for name, stats in profile.by_opening_and_color.items():
        if stats.total >= 3 and stats.win_rate < 0.5:
            problem_openings.append((name, stats))

    problem_openings.sort(key=lambda x: (x[1].win_rate, -x[1].total))

    for name, stats in problem_openings[:5]:
        color = "white" if "(white)" in name else "black"
        clean_name = name.replace(f" ({color})", "")
        recommendations.append(OpeningRecommendation(
            name=clean_name,
            color=color,
            games_played=stats.total,
            win_rate=stats.win_rate,
            problem=f"{stats.wins}W/{stats.losses}L/{stats.draws}D — you lose more than you win",
            suggestion=_opening_suggestion(clean_name, color, stats),
        ))

    # 2. Find openings you never play but face often (knowledge gap)
    # Count what openings opponents play against you
    openings_faced_as_white = defaultdict(int)
    openings_faced_as_black = defaultdict(int)
    for game in games:
        color = game.player_color(username)
        if not color or not game.opening:
            continue
        if color == "white":
            openings_faced_as_white[game.opening] += 1
        else:
            openings_faced_as_black[game.opening] += 1

    # Find frequently faced openings with low win rate
    for opening, count in openings_faced_as_white.items():
        if count >= 3:
            key = f"{opening} (white)"
            if key in profile.by_opening_and_color:
                stats = profile.by_opening_and_color[key]
                if stats.win_rate < 0.4 and not any(r.name == opening for r in recommendations):
                    recommendations.append(OpeningRecommendation(
                        name=opening,
                        color="white",
                        games_played=count,
                        win_rate=stats.win_rate,
                        problem=f"You face this {count} times as white but only win {stats.win_rate*100:.0f}%",
                        suggestion=f"Study the main lines of the {opening}. Focus on typical plans and pawn structures.",
                    ))

    for opening, count in openings_faced_as_black.items():
        if count >= 3:
            key = f"{opening} (black)"
            if key in profile.by_opening_and_color:
                stats = profile.by_opening_and_color[key]
                if stats.win_rate < 0.4 and not any(r.name == opening for r in recommendations):
                    recommendations.append(OpeningRecommendation(
                        name=opening,
                        color="black",
                        games_played=count,
                        win_rate=stats.win_rate,
                        problem=f"You face this {count} times as black but only win {stats.win_rate*100:.0f}%",
                        suggestion=f"Learn a solid response to the {opening}. Focus on development and king safety.",
                    ))

    # 3. Suggest a repertoire based on what you're good at
    strong_openings = []
    for name, stats in profile.by_opening_and_color.items():
        if stats.total >= 3 and stats.win_rate >= 0.6:
            color = "white" if "(white)" in name else "black"
            clean_name = name.replace(f" ({color})", "")
            strong_openings.append((clean_name, color, stats))

    for name, color, stats in sorted(strong_openings, key=lambda x: x[2].total, reverse=True)[:3]:
        if not any(r.name == name and r.color == color for r in recommendations):
            recommendations.append(OpeningRecommendation(
                name=name,
                color=color,
                games_played=stats.total,
                win_rate=stats.win_rate,
                problem=f"{stats.wins}W/{stats.losses}L/{stats.draws}D — this is working for you",
                suggestion=f"Keep playing the {name}! Go deeper — learn the main variations to extend your edge.",
            ))

    return recommendations


def _opening_suggestion(name: str, color: str, stats: Stats) -> str:
    """Generate a specific suggestion for a problem opening."""
    name_lower = name.lower()

    if stats.losses > stats.wins * 2:
        severity = "You're getting crushed here."
    else:
        severity = "This is a trouble spot."

    if color == "white":
        if "gambit" in name_lower:
            return f"{severity} Either learn the refutation of this gambit or switch to declining it."
        if "queen" in name_lower or "d4" in name_lower:
            return f"{severity} Study typical d4 plans: control the center, develop bishops actively, castle early."
        if "king" in name_lower or "e4" in name_lower:
            return f"{severity} Review your development sequence. Make sure you're not making unnecessary pawn moves early."
        return f"{severity} Look up the main ideas and typical plans for white in this opening."
    else:
        if "gambit" in name_lower:
            return f"{severity} Decide whether to accept or decline, and learn the key lines for your choice."
        return f"{severity} Focus on equalizing. Learn the key moves to reach a playable middlegame."


def format_recommendations(recommendations: list[OpeningRecommendation]) -> str:
    """Format opening recommendations as text."""
    if not recommendations:
        return "Not enough game data for opening recommendations (need 3+ games per opening)."

    lines = []
    lines.append("--- Opening Recommendations ---")
    lines.append("")

    # Split into problems and strengths
    problems = [r for r in recommendations if r.win_rate < 0.5]
    strengths = [r for r in recommendations if r.win_rate >= 0.5]

    if problems:
        lines.append("  Openings to Study:")
        for r in problems:
            lines.append(f"    {r.name} (as {r.color}) — {r.games_played} games, {r.win_rate*100:.0f}% win rate")
            lines.append(f"      Problem: {r.problem}")
            lines.append(f"      Action:  {r.suggestion}")
            lines.append("")

    if strengths:
        lines.append("  Your Best Openings (keep playing these):")
        for r in strengths:
            lines.append(f"    {r.name} (as {r.color}) — {r.games_played} games, {r.win_rate*100:.0f}% win rate")
            lines.append(f"      {r.suggestion}")
            lines.append("")

    return "\n".join(lines)
