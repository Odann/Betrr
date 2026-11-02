"""Final scores and win/loss grading for moneylines, spreads and totals."""

from datetime import datetime, timedelta

from . import config
from .analyze import american_to_decimal
from .odds_client import parse_time


def settle(market: str, side: str, point, home: float, away: float, three_way: bool = False) -> str:
    """'win', 'loss' or 'push' for one bet, given the final score."""
    market = market or "h2h"
    if market == "totals":
        total = home + away
        if total == point:
            return "push"
        return "win" if (total > point) == (side == "over") else "loss"
    if market == "spreads":
        margin = (home - away) if side == "home" else (away - home)
        result = margin + point
        return "push" if result == 0 else "win" if result > 0 else "loss"
    # moneyline
    if home == away:
        if side == "draw":
            return "win"
        return "loss" if three_way else "push"
    winner = "home" if home > away else "away"
    return "win" if side == winner else "loss"


def record_finals(scores: dict, sport: str, events: list[dict]) -> int:
    """Store completed games from a scores response. Returns how many were new."""
    new = 0
    for e in events:
        if not (e.get("completed") and e.get("scores")):
            continue
        try:
            pts = {s["name"]: float(s["score"]) for s in e["scores"]}
            home, away = pts[e["home_team"]], pts[e["away_team"]]
        except (KeyError, TypeError, ValueError):
            continue
        if e["id"] not in scores["finals"]:
            new += 1
        scores["finals"][e["id"]] = {
            "sport": sport, "home_team": e["home_team"], "away_team": e["away_team"],
            "home_score": home, "away_score": away, "start_time_utc": e["commence_time"],
        }
        scores["awaiting"].pop(e["id"], None)
    return new


def sports_needing_scores(scores: dict, now: datetime) -> set[str]:
    """Sports with a game that should be over but has no final score yet."""
    due = timedelta(hours=config.GRADE_AFTER_HOURS)
    return {g["sport"] for g in scores["awaiting"].values()
            if now - parse_time(g["start_time_utc"]) >= due}


def prune(scores: dict, now: datetime) -> None:
    """Drop games too old to look up or to keep."""
    lookup_limit = timedelta(days=config.SCORES_DAYS_BACK)
    keep_limit = timedelta(days=config.KEEP_SCORES_DAYS)
    scores["awaiting"] = {k: v for k, v in scores["awaiting"].items()
                          if now - parse_time(v["start_time_utc"]) <= lookup_limit}
    scores["finals"] = {k: v for k, v in scores["finals"].items()
                        if now - parse_time(v["start_time_utc"]) <= keep_limit}


def grade_history(history: list[dict], finals: dict, now: datetime) -> int:
    """Fill in result/profit for logged picks whose games have final scores."""
    graded = 0
    for p in history:
        if p.get("result") is not None:
            continue
        f = finals.get(p["event_id"])
        if f:
            result = settle(p.get("market", "h2h"), p["side"], p.get("point"),
                            f["home_score"], f["away_score"], p.get("three_way", False))
            p["result"] = result
            p["final_score"] = (f"{f['away_team']} {f['away_score']:g}, "
                                f"{f['home_team']} {f['home_score']:g}")
            p["profit"] = round(config.STAKE * (american_to_decimal(p["odds"]) - 1) if result == "win"
                                else -config.STAKE if result == "loss" else 0, 2)
            graded += 1
        elif now - parse_time(p["start_time_utc"]) > timedelta(days=config.SCORES_DAYS_BACK):
            p["result"], p["profit"] = "ungraded", 0   # too old for the scores lookup
    return graded
