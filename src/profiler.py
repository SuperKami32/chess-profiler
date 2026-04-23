"""Weakness profiling — aggregate stats across games."""

from collections import defaultdict
from dataclasses import dataclass, field

from .models import Game


@dataclass
class Stats:
    wins: int = 0
    losses: int = 0
    draws: int = 0

    @property
    def total(self) -> int:
        return self.wins + self.losses + self.draws

    @property
    def win_rate(self) -> float:
        return self.wins / self.total if self.total else 0.0

    def record(self, result: str):
        if result == "win":
            self.wins += 1
        elif result == "loss":
            self.losses += 1
        else:
            self.draws += 1

    def __str__(self) -> str:
        pct = self.win_rate * 100
        return f"{self.wins}W / {self.losses}L / {self.draws}D  ({pct:.0f}% win rate, {self.total} games)"


@dataclass
class Profile:
    username: str
    total_games: int = 0

    overall: Stats = field(default_factory=Stats)
    by_color: dict[str, Stats] = field(default_factory=lambda: defaultdict(Stats))
    by_time_class: dict[str, Stats] = field(default_factory=lambda: defaultdict(Stats))
    by_opening: dict[str, Stats] = field(default_factory=lambda: defaultdict(Stats))
    by_opening_and_color: dict[str, Stats] = field(default_factory=lambda: defaultdict(Stats))

    accuracy_sum: float = 0.0
    accuracy_count: int = 0

    rating_history: list[tuple[str, str, int]] = field(default_factory=list)
    # (date, time_class, rating)

    # Phase 1 additions
    loss_types: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    # e.g. {"checkmated": 30, "timeout": 15, "resigned": 40}

    accuracy_history: list[tuple[str, float]] = field(default_factory=list)
    # (date, accuracy) for trend tracking

    by_game_length: dict[str, Stats] = field(default_factory=lambda: defaultdict(Stats))
    # "short" (≤15 moves), "medium" (16-30), "long" (31+)

    move_count_results: list[tuple[int, str]] = field(default_factory=list)
    # (move_count, result) for detailed analysis

    def avg_accuracy(self) -> float | None:
        return self.accuracy_sum / self.accuracy_count if self.accuracy_count else None

    def recent_accuracy(self, n: int = 20) -> float | None:
        """Average accuracy of last N games that have accuracy data."""
        if not self.accuracy_history:
            return None
        recent = self.accuracy_history[-n:]
        return sum(a for _, a in recent) / len(recent)


def build_profile(username: str, games: list[Game]) -> Profile:
    """Build a weakness profile from a list of games."""
    profile = Profile(username=username, total_games=len(games))

    for game in games:
        if game.rules != "chess":
            continue

        result = game.player_result(username)
        if result is None:
            continue

        color = game.player_color(username)

        profile.overall.record(result)
        profile.by_color[color].record(result)
        profile.by_time_class[game.time_class].record(result)

        if game.opening:
            profile.by_opening[game.opening].record(result)
            key = f"{game.opening} ({color})"
            profile.by_opening_and_color[key].record(result)

        acc = game.player_accuracy(username)
        if acc is not None:
            profile.accuracy_sum += acc
            profile.accuracy_count += 1
            profile.accuracy_history.append((game.date, acc))

        rating = game.player_rating(username)
        if rating is not None:
            profile.rating_history.append((game.date, game.time_class, rating))

        # Loss type tracking
        if result == "loss":
            raw = game.player_raw_result(username)
            if raw:
                profile.loss_types[raw] += 1

        # Game length tracking
        moves = game.move_count()
        if moves is not None:
            if moves <= 15:
                length_bucket = "short (≤15 moves)"
            elif moves <= 30:
                length_bucket = "medium (16-30 moves)"
            else:
                length_bucket = "long (31+ moves)"
            profile.by_game_length[length_bucket].record(result)
            profile.move_count_results.append((moves, result))

    return profile


def format_profile(profile: Profile) -> str:
    """Format a profile as a readable report."""
    lines = []
    lines.append(f"=== Chess Profile: {profile.username} ===")
    lines.append(f"Total games analyzed: {profile.total_games}")
    lines.append("")

    # Overall
    lines.append(f"Overall:  {profile.overall}")
    avg_acc = profile.avg_accuracy()
    if avg_acc is not None:
        recent_acc = profile.recent_accuracy(20)
        lines.append(f"Average accuracy: {avg_acc:.1f}%")
        if recent_acc is not None:
            delta = recent_acc - avg_acc
            trend = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            lines.append(f"Recent accuracy (last 20): {recent_acc:.1f}% ({trend} {abs(delta):.1f})")
    lines.append("")

    # By color
    lines.append("--- By Color ---")
    for color in ("white", "black"):
        if color in profile.by_color:
            lines.append(f"  {color.capitalize():6s}: {profile.by_color[color]}")
    lines.append("")

    # By time control
    lines.append("--- By Time Control ---")
    for tc in sorted(profile.by_time_class, key=lambda k: profile.by_time_class[k].total, reverse=True):
        lines.append(f"  {tc:8s}: {profile.by_time_class[tc]}")
    lines.append("")

    # Rating range by time class
    if profile.rating_history:
        lines.append("--- Rating Range ---")
        by_tc: dict[str, list[int]] = defaultdict(list)
        for _, tc, rating in profile.rating_history:
            by_tc[tc].append(rating)
        for tc in sorted(by_tc):
            ratings = by_tc[tc]
            lines.append(f"  {tc:8s}: {min(ratings)} - {max(ratings)} (current: {ratings[-1]})")
        lines.append("")

    # How you lose
    if profile.loss_types:
        lines.append("--- How You Lose ---")
        total_losses = sum(profile.loss_types.values())
        for loss_type, count in sorted(profile.loss_types.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_losses * 100
            bar = "█" * int(pct / 2)
            lines.append(f"  {loss_type:14s}: {count:3d} ({pct:.0f}%) {bar}")
        lines.append("")

    # Game length analysis
    length_order = ["short (≤15 moves)", "medium (16-30 moves)", "long (31+ moves)"]
    active_lengths = {k: v for k, v in profile.by_game_length.items() if v.total > 0}
    if active_lengths:
        lines.append("--- By Game Length ---")
        for length in length_order:
            if length in active_lengths:
                lines.append(f"  {length:22s}: {active_lengths[length]}")
        # Average moves in wins vs losses
        win_moves = [m for m, r in profile.move_count_results if r == "win"]
        loss_moves = [m for m, r in profile.move_count_results if r == "loss"]
        if win_moves and loss_moves:
            lines.append(f"  Avg moves in wins:  {sum(win_moves)/len(win_moves):.0f}")
            lines.append(f"  Avg moves in losses: {sum(loss_moves)/len(loss_moves):.0f}")
        lines.append("")

    # Worst openings (≥3 games, sorted by win rate ascending)
    openings_with_enough_games = {
        name: stats for name, stats in profile.by_opening_and_color.items()
        if stats.total >= 2
    }
    if openings_with_enough_games:
        lines.append("--- Weakest Openings (2+ games) ---")
        sorted_openings = sorted(openings_with_enough_games.items(), key=lambda x: x[1].win_rate)
        for name, stats in sorted_openings[:10]:
            lines.append(f"  {name}")
            lines.append(f"    {stats}")
        lines.append("")

    # Best openings
    if openings_with_enough_games:
        lines.append("--- Strongest Openings (2+ games) ---")
        sorted_openings = sorted(openings_with_enough_games.items(), key=lambda x: x[1].win_rate, reverse=True)
        for name, stats in sorted_openings[:10]:
            lines.append(f"  {name}")
            lines.append(f"    {stats}")

    return "\n".join(lines)
