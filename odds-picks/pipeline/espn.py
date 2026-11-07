"""
Final scores from ESPN's public scoreboard (free, no key).

ESPN's scoreboard is unofficial: it has no published terms or guarantees and
can change without notice, so anything it can't match falls back to The Odds
API's scores endpoint.

    https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates=YYYYMMDD

It takes one date at a time (ranges return 400), in US Eastern dates.
"""

import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"
PATHS = {
    "icehockey_nhl": "hockey/nhl",
    "basketball_nba": "basketball/nba",
    "americanfootball_nfl": "football/nfl",
}
EASTERN = ZoneInfo("America/New_York")


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def nickname(name: str) -> str:
    """Last word of the team name, which is unique within each league."""
    return norm(name).split(" ")[-1]


def eastern_date(start_utc: str) -> str:
    return datetime.fromisoformat(start_utc).astimezone(EASTERN).strftime("%Y%m%d")


class ESPN:
    def __init__(self, session: requests.Session | None = None):
        self.http = session or requests.Session()
        self.http.headers["User-Agent"] = "picks-board/1.0"
        self.cache: dict[tuple, list] = {}
        self.calls = 0

    def scoreboard(self, sport: str, yyyymmdd: str) -> list[dict]:
        """Completed and scheduled games for one league on one Eastern date."""
        key = (sport, yyyymmdd)
        if key in self.cache:
            return self.cache[key]
        path = PATHS.get(sport)
        if not path:
            return []
        try:
            r = self.http.get(BASE.format(path=path), params={"dates": yyyymmdd}, timeout=15)
            r.raise_for_status()
            events = r.json().get("events", [])
        except (requests.RequestException, ValueError) as e:
            print(f"ESPN {sport} {yyyymmdd}: {e}", file=sys.stderr)
            events = []
        self.calls += 1
        time.sleep(0.2)   # be polite
        games = []
        for e in events:
            try:
                comp = e["competitions"][0]
                teams = {c["homeAway"]: c for c in comp["competitors"]}
                games.append({
                    "espn_id": e["id"],
                    "start_time_utc": e["date"],
                    "completed": bool(e["status"]["type"]["completed"]),
                    "home_team": teams["home"]["team"]["displayName"],
                    "away_team": teams["away"]["team"]["displayName"],
                    "home_score": float(teams["home"].get("score") or 0),
                    "away_score": float(teams["away"].get("score") or 0),
                    "neutral": bool(comp.get("neutralSite")),
                })
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        self.cache[key] = games
        return games

    def find_final(self, sport: str, home: str, away: str, start_utc: str) -> dict | None:
        """The completed ESPN game matching these teams around this start time."""
        when = datetime.fromisoformat(start_utc)
        dates = {eastern_date(start_utc), eastern_date((when + timedelta(hours=6)).isoformat())}
        h, a = nickname(home), nickname(away)
        for d in sorted(dates):
            for g in self.scoreboard(sport, d):
                if not g["completed"]:
                    continue
                if nickname(g["home_team"]) == h and nickname(g["away_team"]) == a:
                    gap = abs((datetime.fromisoformat(g["start_time_utc"].replace("Z", "+00:00")) - when).total_seconds())
                    if gap <= 12 * 3600:
                        return g
        return None
