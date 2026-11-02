"""Small client for The Odds API (v4), plus parsing into a simple game format."""

from datetime import datetime, timezone

import requests

BASE_URL = "https://api.the-odds-api.com/v4"


class OddsAPIError(RuntimeError):
    pass


class OddsAPI:
    def __init__(self, api_key: str):
        if not api_key:
            raise OddsAPIError("ODDS_API_KEY is not set.")
        self.api_key = api_key
        self.remaining: int | None = None   # credits left this month, from response headers
        self.used_this_run = 0

    def _get(self, path: str, params: dict | None = None):
        resp = requests.get(f"{BASE_URL}{path}",
                            params={"apiKey": self.api_key, **(params or {})}, timeout=15)
        if resp.status_code != 200:
            raise OddsAPIError(f"{path} returned {resp.status_code}: {resp.text[:200]}")
        if resp.headers.get("x-requests-remaining") is not None:
            self.remaining = int(float(resp.headers["x-requests-remaining"]))
        self.used_this_run += int(float(resp.headers.get("x-requests-last", 0) or 0))
        return resp.json()

    def active_sports(self) -> set[str]:
        """Keys of in-season sports. Free: doesn't use credits."""
        return {s["key"] for s in self._get("/sports")}

    def odds(self, sport: str, region: str) -> list:
        """Moneyline odds for upcoming games. Costs 1 credit."""
        return self._get(f"/sports/{sport}/odds", {
            "regions": region, "markets": "h2h",
            "oddsFormat": "american", "dateFormat": "iso",
        })

    def scores(self, sport: str, days_from: int) -> list:
        """Scores including finished games from the last `days_from` days. Costs 2 credits."""
        return self._get(f"/sports/{sport}/scores", {"daysFrom": days_from, "dateFormat": "iso"})


def parse_time(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def parse_games(events: list, now: datetime | None = None) -> list[dict]:
    """Turn raw odds events into games with each book's home/away/draw moneyline."""
    now = now or datetime.now(timezone.utc)
    games = []
    for ev in events:
        start = parse_time(ev["commence_time"])
        if start <= now:
            continue  # already started; live odds aren't useful here
        lines = []
        for book in ev.get("bookmakers", []):
            h2h = next((m for m in book.get("markets", []) if m["key"] == "h2h"), None)
            if not h2h:
                continue
            prices = {o["name"]: o["price"] for o in h2h["outcomes"]}
            lines.append({
                "bookmaker": book["title"],
                "home": prices.get(ev["home_team"]),
                "away": prices.get(ev["away_team"]),
                "draw": prices.get("Draw"),
            })
        if lines:
            games.append({
                "event_id": ev["id"],
                "home_team": ev["home_team"],
                "away_team": ev["away_team"],
                "start_time_utc": start.isoformat(),
                "lines": lines,
            })
    return games
