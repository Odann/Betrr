"""
One update run: fetch odds, price every game's main bets, find picks, log
them, collect final scores, grade, and write the JSON files the dashboard reads.

    ODDS_API_KEY=yourkey python -m pipeline.update

GitHub Actions runs this on a schedule (see .github/workflows/update-picks.yml).
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from . import config
from .analyze import analyze_games
from .edges import find_edges
from .espn import ESPN
from .grade import grade_history, prune, record_espn_finals, record_finals, sports_needing_scores
from .odds_client import OddsAPI, OddsAPIError, parse_games, parse_time

PICKS_FILE = config.DATA_DIR / "picks.json"
BOARD_FILE = config.DATA_DIR / "board.json"
HISTORY_FILE = config.DATA_DIR / "history.json"
SCORES_FILE = config.DATA_DIR / "scores.json"
SNAPSHOT_FILE = config.DATA_DIR / "snapshots.json"
CLOSES_FILE = config.DATA_DIR / "closes.json"
EDGES_FILE = config.DATA_DIR / "edges.json"


def load(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, data, indent=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=indent))
    tmp.replace(path)


def dedupe_history(picks: list[dict]) -> list[dict]:
    """
    Picks logged before spreads and totals were added used ids like
    "event|away"; newer ones use "event|h2h|away". Bring old ids up to date and
    keep one entry per pick, preferring a graded one.
    """
    kept: dict[str, dict] = {}
    for p in picks:
        if p["id"].count("|") == 1:
            p["market"] = p.get("market") or "h2h"
            p["id"] = f"{p['event_id']}|{p['market']}|{p['side']}"
        prev = kept.get(p["id"])
        if prev is None or (prev.get("result") is None and p.get("result") is not None):
            kept[p["id"]] = p
    return list(kept.values())


def credits_ok(api: OddsAPI, cost: int) -> bool:
    return api.remaining is None or api.remaining - cost >= config.CREDIT_FLOOR


def update_closes(closes: dict, board: list[dict], now: datetime) -> None:
    """
    Latest fair price for every selection on the board. Once a game starts it
    drops off the board, so its last entry here is the closing line.
    """
    for g in board:
        for market, m in g["markets"].items():
            for s in m["selections"]:
                if s.get("fair_prob") is None:
                    continue
                closes[f"{g['event_id']}|{market}|{s['key']}"] = {
                    "fair": s["fair_prob"], "odds": s["odds"], "book": s["book"], "point": s["point"],
                    "at": now.isoformat(), "start": g["start_time_utc"],
                }
    keep = timedelta(days=config.KEEP_CLOSES_DAYS)
    for k in [k for k, c in closes.items() if now - parse_time(c["start"]) > keep]:
        del closes[k]


def run(api: OddsAPI, now: datetime | None = None, espn: ESPN | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    espn = espn or ESPN()
    old_picks = load(PICKS_FILE, {})
    old_board = load(BOARD_FILE, {})
    history = load(HISTORY_FILE, {"picks": []})
    if old_picks.get("sample"):
        old_picks, old_board = {}, {}
    if history.get("sample"):
        history = {"picks": []}
    history["picks"] = dedupe_history(history["picks"])
    scores = load(SCORES_FILE, {"finals": {}, "awaiting": {}})
    snapshots = load(SNAPSHOT_FILE, {})
    closes = load(CLOSES_FILE, {})
    prev_board = {g["event_id"]: g for g in old_board.get("games", [])}

    notes = []
    try:
        active = api.active_sports()
    except OddsAPIError as e:
        print(f"Couldn't check which sports are in season: {e}", file=sys.stderr)
        active = set(config.SPORTS)

    picks, board, checked, off_season = [], [], [], []
    for sport in config.SPORTS:
        if sport not in active:
            off_season.append(sport)
            continue

        def carry_over():
            picks.extend(p for p in old_picks.get("picks", [])
                         if p["sport"] == sport and parse_time(p["start_time_utc"]) > now)
            board.extend(g for g in old_board.get("games", [])
                         if g["sport"] == sport and parse_time(g["start_time_utc"]) > now)

        cost = len(config.MARKETS)
        if not credits_ok(api, cost):
            notes.append("API credits are almost used up, so odds weren't refreshed.")
            carry_over()
            continue
        try:
            events = api.odds(sport, config.REGION, config.MARKETS)
        except OddsAPIError as e:
            print(f"{sport}: {e}", file=sys.stderr)
            notes.append(f"Couldn't refresh {sport}; showing its previous odds.")
            carry_over()
            continue

        games = parse_games(events, now)
        prev = snapshots.get(sport, {}).get("lines", {})
        found, fair, sport_board = analyze_games(games, sport, prev, prev_board, now.isoformat())
        snapshots[sport] = {"taken_at": now.isoformat(), "lines": fair}
        picks += found
        board += sport_board
        checked.append(sport)

    picks.sort(key=lambda p: (p["confidence"], p["expected_value"]), reverse=True)
    board.sort(key=lambda g: g["start_time_utc"])

    # Log each pick the first time it appears, at the odds shown then.
    logged = {p["id"] for p in history["picks"]}
    for p in picks:
        if p["id"] not in logged:
            history["picks"].append({**p, "logged_at": now.isoformat(), "result": None, "profit": None})

    # Every game on the board (and every pending pick) needs a final score later,
    # both for grading picks and for bets saved in the browser.
    for g in board + [p for p in history["picks"] if p.get("result") is None]:
        if g["event_id"] in scores["finals"]:
            continue
        entry = scores["awaiting"].setdefault(g["event_id"], {"sport": g["sport"], "start_time_utc": g["start_time_utc"]})
        entry.setdefault("home_team", g["home_team"])
        entry.setdefault("away_team", g["away_team"])
    prune(scores, now)
    update_closes(closes, board, now)

    # Final scores: ESPN first (free), The Odds API only for what ESPN can't match.
    from_espn = record_espn_finals(scores, espn, now)
    print(f"ESPN: {from_espn} final score(s) in {espn.calls} call(s)")
    # Fallback costs 2 credits per sport, so only for games ESPN still can't
    # match half a day after they should have finished.
    for sport in sorted(sports_needing_scores(scores, now, extra_hours=12)):
        if not credits_ok(api, 2):
            notes.append("Skipped checking final scores to save API credits.")
            break
        try:
            new = record_finals(scores, sport, api.scores(sport, config.SCORES_DAYS_BACK))
            print(f"{sport}: {new} new final score(s)")
        except OddsAPIError as e:
            print(f"{sport} scores: {e}", file=sys.stderr)

    graded = grade_history(history["picks"], scores["finals"], now, closes)
    prune(scores, now)
    edges = find_edges(board)

    meta = {
        "generated_at": now.isoformat(),
        "sports_checked": checked,
        "off_season": off_season,
        "credits_remaining": api.remaining,
        "credits_used_this_run": api.used_this_run,
        "notes": sorted(set(notes)),
        "stake": config.STAKE,
    }
    save(PICKS_FILE, {**meta, "picks": picks})
    save(BOARD_FILE, {"generated_at": meta["generated_at"], "games": board}, indent=None)
    save(HISTORY_FILE, {"stake": config.STAKE, "picks": history["picks"]})
    save(SCORES_FILE, scores)
    save(SNAPSHOT_FILE, snapshots, indent=None)
    save(CLOSES_FILE, closes, indent=None)
    save(EDGES_FILE, {"generated_at": meta["generated_at"], **edges})
    print(f"{len(picks)} pick(s), {len(board)} game(s) from {', '.join(checked) or 'no sports'}; "
          f"graded {graded}; used {api.used_this_run} credit(s), {api.remaining} left.")
    return meta


if __name__ == "__main__":
    try:
        run(OddsAPI(os.getenv("ODDS_API_KEY", "")))
    except OddsAPIError as e:
        sys.exit(str(e))
