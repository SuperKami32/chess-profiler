"""Chess.com public API client."""

import requests

BASE_URL = "https://api.chess.com/pub"
HEADERS = {"User-Agent": "chess-profiler/0.1"}


def get_archives(username: str) -> list[str]:
    """Return list of monthly archive URLs for a player."""
    resp = requests.get(f"{BASE_URL}/player/{username}/games/archives", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["archives"]


def get_games(archive_url: str) -> list[dict]:
    """Fetch all games from a single monthly archive URL."""
    resp = requests.get(archive_url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["games"]


def get_all_games(username: str, last_n_months: int | None = None) -> list[dict]:
    """Fetch games across all (or last N) monthly archives."""
    archives = get_archives(username)
    if last_n_months:
        archives = archives[-last_n_months:]

    all_games = []
    for url in archives:
        all_games.extend(get_games(url))
    return all_games
