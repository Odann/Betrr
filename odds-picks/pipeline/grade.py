"""Grades logged picks once their games have final scores."""

from datetime import datetime, timedelta

from . import config
from .analyze import american_to_decimal
from .odds_client import parse_time


def needs_grading(pick: dict, now: datetime) -> bool:
    started = parse_time(pick["start_time_utc"])
    too_old = now - started > timedelta(days=config.SCORES_DAYS_BACK)
    return (pick.get("result") is None and not too_old
            and now - started >= timedelta(hours=config.GRADE_AFTER_HOURS))


def expire_old(history: list, now: datetime) -> None:
    """Picks too old for the scores lookup can't be graded any more."""
    for p in history:
        if p.get("result") is None and now - parse_time(p["start_time_utc"]) > timedelta(days=config.SCORES_DAYS_BACK):
            p["result"] = "ungraded"
            p["profit"] = 0


def grade_picks(pending: list[dict], score_events: list[dict]) -> int:
    """Fill in result/profit for pending picks whose games finished. Returns count graded."""
    finished = {e["id"]: e for e in score_events if e.get("completed") and e.get("scores")}
    graded = 0
    for p in pending:
        ev = finished.get(p["event_id"])
        if not ev:
            continue
        try:
            pts = {s["name"]: float(s["score"]) for s in ev["scores"]}
            home, away = pts[ev["home_team"]], pts[ev["away_team"]]
        except (KeyError, TypeError, ValueError):
            continue

        if home == away:
            outcome = "draw"
        else:
            outcome = "home" if home > away else "away"

        if p["side"] == outcome:
            result = "win"
        elif outcome == "draw" and p["side"] != "draw" and not _has_draw_market(p):
            result = "push"          # tie in a two-way market: stake returned
        else:
            result = "loss"

        p["result"] = result
        p["final_score"] = f"{p['away_team']} {away:g}, {p['home_team']} {home:g}"
        p["profit"] = round(
            config.STAKE * (american_to_decimal(p["odds"]) - 1) if result == "win"
            else -config.STAKE if result == "loss" else 0, 2)
        graded += 1
    return graded


def _has_draw_market(p: dict) -> bool:
    return p.get("three_way", False)
