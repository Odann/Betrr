"""
One update run: fetch odds, find picks, log them, grade finished ones,
and write the JSON files the dashboard reads.

    ODDS_API_KEY=yourkey python -m pipeline.update

GitHub Actions runs this on a schedule (see .github/workflows/update-picks.yml).
"""

import json
import os
import sys
from datetime import datetime, timezone

from . import config
from .analyze import analyze_games
from .grade import expire_old, grade_picks, needs_grading
from .odds_client import OddsAPI, OddsAPIError, parse_games, parse_time

PICKS_FILE = config.DATA_DIR / "picks.json"
HISTORY_FILE = config.DATA_DIR / "history.json"
SNAPSHOT_FILE = config.DATA_DIR / "snapshots.json"


def load(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def credits_ok(api: OddsAPI, cost: int) -> bool:
    return api.remaining is None or api.remaining - cost >= config.CREDIT_FLOOR


def run(api: OddsAPI, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    old = load(PICKS_FILE, {})
    if old.get("sample"):
        old = {}  # first real run: drop the sample data
    history = load(HISTORY_FILE, {"picks": []})
    if history.get("sample"):
        history = {"picks": []}
    snapshots = load(SNAPSHOT_FILE, {})

    notes = []
    try:
        active = api.active_sports()
    except OddsAPIError as e:
        print(f"Couldn't check which sports are in season: {e}", file=sys.stderr)
        active = set(config.SPORTS)

    picks, checked, off_season = [], [], []
    for sport in config.SPORTS:
        if sport not in active:
            off_season.append(sport)
            continue
        carry = [p for p in old.get("picks", [])
                 if p["sport"] == sport and parse_time(p["start_time_utc"]) > now]
        if not credits_ok(api, 1):
            notes.append("API credits are almost used up, so these picks weren't refreshed.")
            picks += carry
            continue
        try:
            events = api.odds(sport, config.REGION)
        except OddsAPIError as e:
            print(f"{sport}: {e}", file=sys.stderr)
            notes.append(f"Couldn't refresh {sport}; showing its previous picks.")
            picks += carry
            continue

        games = parse_games(events, now)
        prev_fair = snapshots.get(sport, {}).get("games", {})
        found, fair = analyze_games(games, sport, prev_fair)
        snapshots[sport] = {"taken_at": now.isoformat(), "games": fair}
        picks += found
        checked.append(sport)

    picks.sort(key=lambda p: (p["confidence"], p["expected_value"]), reverse=True)

    # Log each pick the first time it appears, at the odds shown then.
    logged = {p["id"] for p in history["picks"]}
    for p in picks:
        if p["id"] not in logged:
            history["picks"].append({**p, "logged_at": now.isoformat(),
                                     "result": None, "profit": None})

    # Grade finished games, one scores lookup per sport that needs it.
    expire_old(history["picks"], now)
    pending = [p for p in history["picks"] if needs_grading(p, now)]
    for sport in sorted({p["sport"] for p in pending}):
        if not credits_ok(api, 2):
            notes.append("Skipped checking results to save API credits.")
            break
        try:
            events = api.scores(sport, config.SCORES_DAYS_BACK)
        except OddsAPIError as e:
            print(f"{sport} scores: {e}", file=sys.stderr)
            continue
        n = grade_picks([p for p in pending if p["sport"] == sport], events)
        print(f"{sport}: graded {n} pick(s)")

    out = {
        "generated_at": now.isoformat(),
        "sports_checked": checked,
        "off_season": off_season,
        "credits_remaining": api.remaining,
        "credits_used_this_run": api.used_this_run,
        "notes": sorted(set(notes)),
        "stake": config.STAKE,
        "picks": picks,
    }
    save(PICKS_FILE, out)
    save(HISTORY_FILE, {"stake": config.STAKE, "picks": history["picks"]})
    save(SNAPSHOT_FILE, snapshots)
    print(f"{len(picks)} pick(s) from {', '.join(checked) or 'no sports'}; "
          f"used {api.used_this_run} credit(s), {api.remaining} left.")
    return out


if __name__ == "__main__":
    try:
        run(OddsAPI(os.getenv("ODDS_API_KEY", "")))
    except OddsAPIError as e:
        sys.exit(str(e))
