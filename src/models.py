"""Data models for parsed Chess.com games."""

from dataclasses import dataclass


@dataclass
class Game:
    url: str
    date: str
    time_control: str
    time_class: str  # bullet, blitz, rapid, daily
    rated: bool
    rules: str

    white_username: str
    white_rating: int
    white_result: str

    black_username: str
    black_rating: int
    black_result: str

    white_accuracy: float | None
    black_accuracy: float | None

    opening: str | None  # cleaned opening name
    eco_url: str | None  # raw Chess.com opening URL
    pgn: str | None

    def player_color(self, username: str) -> str | None:
        lower = username.lower()
        if self.white_username.lower() == lower:
            return "white"
        if self.black_username.lower() == lower:
            return "black"
        return None

    def player_result(self, username: str) -> str | None:
        """Return 'win', 'loss', or 'draw' from the player's perspective."""
        color = self.player_color(username)
        if color is None:
            return None
        result = self.white_result if color == "white" else self.black_result
        if result == "win":
            return "win"
        if result in ("checkmated", "timeout", "resigned", "abandoned"):
            return "loss"
        # stalemate, agreed, repetition, insufficient, 50move, timevsinsufficient
        return "draw"

    def player_rating(self, username: str) -> int | None:
        color = self.player_color(username)
        if color == "white":
            return self.white_rating
        if color == "black":
            return self.black_rating
        return None

    def player_accuracy(self, username: str) -> float | None:
        color = self.player_color(username)
        if color == "white":
            return self.white_accuracy
        if color == "black":
            return self.black_accuracy
        return None

    def opponent_username(self, username: str) -> str | None:
        color = self.player_color(username)
        if color == "white":
            return self.black_username
        if color == "black":
            return self.white_username
        return None

    def player_raw_result(self, username: str) -> str | None:
        """Return the raw Chess.com result string (win, checkmated, timeout, resigned, etc.)."""
        color = self.player_color(username)
        if color == "white":
            return self.white_result
        if color == "black":
            return self.black_result
        return None

    def move_count(self) -> int | None:
        """Extract total number of full moves from PGN."""
        if not self.pgn:
            return None
        # Find the last move number in the PGN (e.g., "34. Qxf7#")
        # Move numbers appear as "N." in the move text after the headers
        import re
        # Get everything after the headers (lines not starting with [)
        moves_section = ""
        for line in self.pgn.split("\n"):
            if line and not line.startswith("["):
                moves_section += line + " "
        move_numbers = re.findall(r"(\d+)\.", moves_section)
        if move_numbers:
            return int(move_numbers[-1])
        return None


def parse_opening(eco_url: str | None) -> str | None:
    """Extract readable opening name from Chess.com ECO URL.

    e.g. '.../openings/Queens-Pawn-Opening-Accelerated-London-System'
         -> "Queens Pawn Opening Accelerated London System"
    """
    if not eco_url:
        return None
    # URL looks like https://www.chess.com/openings/Sicilian-Defense-Closed-2...Nc6
    path = eco_url.rsplit("/", 1)[-1]
    # Remove move suffixes like "-2...Nc6" or "-3.d4"
    # These appear after the opening name with a move number
    parts = path.split("-")
    cleaned = []
    for part in parts:
        # Stop if we hit a move number like "2...Nc6" or "3.d4"
        if part and part[0].isdigit():
            break
        cleaned.append(part)
    return " ".join(cleaned) if cleaned else path.replace("-", " ")


def game_from_api(data: dict) -> Game:
    """Convert a raw Chess.com API game dict into a Game."""
    accuracies = data.get("accuracies", {})
    eco_url = data.get("eco")

    # Extract date from PGN header or use end_time
    pgn = data.get("pgn", "")
    date = ""
    for line in pgn.split("\n"):
        if line.startswith("[Date "):
            date = line.split('"')[1]
            break

    return Game(
        url=data.get("url", ""),
        date=date,
        time_control=data.get("time_control", ""),
        time_class=data.get("time_class", ""),
        rated=data.get("rated", False),
        rules=data.get("rules", "chess"),
        white_username=data["white"]["username"],
        white_rating=data["white"]["rating"],
        white_result=data["white"]["result"],
        black_username=data["black"]["username"],
        black_rating=data["black"]["rating"],
        black_result=data["black"]["result"],
        white_accuracy=accuracies.get("white"),
        black_accuracy=accuracies.get("black"),
        opening=parse_opening(eco_url),
        eco_url=eco_url,
        pgn=pgn,
    )
