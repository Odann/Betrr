"""
Finds picks in a sport's games.

1. Fair probability: strip each book's margin (the "vig") so its outcome
   probabilities add to 100%, then average across books.
2. Value bet: the best available price pays more than that fair probability
   says it should:  EV = fair_prob * decimal_odds - 1  >=  MIN_EDGE
3. Line move: the fair probability moved by MOVE_THRESHOLD or more since the
   previous run. A move toward a side can qualify it on its own (if the price
   still isn't a losing bet); a move against a pick lowers its confidence.
4. Confidence (0-100): edge size, number of books, how closely they agree,
   and line movement.
"""

from statistics import mean, pstdev

from . import config


def american_to_prob(price: int) -> float:
    return 100 / (price + 100) if price > 0 else -price / (-price + 100)


def american_to_decimal(price: int) -> float:
    return 1 + price / 100 if price > 0 else 1 + 100 / -price


def no_vig(line: dict) -> dict | None:
    sides = {k: line[k] for k in ("home", "away", "draw") if line.get(k) is not None}
    if len(sides) < 2:
        return None
    raw = {k: american_to_prob(v) for k, v in sides.items()}
    total = sum(raw.values())
    return {k: p / total for k, p in raw.items()}


def confidence_score(ev: float, n_books: int, spread: float, movement: float | None) -> int:
    score = min(max(ev, 0) / 0.08, 1) * 50          # up to 50: edge size (maxes at 8%)
    score += min(n_books / 8, 1) * 20                # up to 20: number of books (maxes at 8)
    score += (1 - min(spread / 0.04, 1)) * 15        # up to 15: books agree with each other
    if movement is not None and abs(movement) >= config.MOVE_THRESHOLD:
        score += 15 if movement > 0 else -15         # +/-15: line moving with or against
    return round(max(0, min(100, score)))


def rating(score: int) -> str:
    return "High" if score >= 70 else "Medium" if score >= 45 else "Low"


def analyze_games(games: list[dict], sport: str, previous_fair: dict) -> tuple[list, dict]:
    """
    Returns (picks, fair_by_event). `previous_fair` is {event_id: {side: prob}}
    from the last run, used for line movement.
    """
    picks, fair_by_event = [], {}

    for g in games:
        per_book = [p for p in (no_vig(l) for l in g["lines"]) if p]
        if len(per_book) < config.MIN_BOOKS:
            continue

        fair = {side: mean(b[side] for b in per_book if side in b)
                for side in ("home", "away", "draw") if any(side in b for b in per_book)}
        fair_by_event[g["event_id"]] = fair
        team_for = {"home": g["home_team"], "away": g["away_team"], "draw": "Draw"}

        for side, fair_p in fair.items():
            prices = [(l[side], l["bookmaker"]) for l in g["lines"] if l.get(side) is not None]
            best_price, best_book = max(prices, key=lambda x: american_to_decimal(x[0]))
            ev = fair_p * american_to_decimal(best_price) - 1
            spread = pstdev([b[side] for b in per_book if side in b])

            prev = previous_fair.get(g["event_id"], {}).get(side)
            movement = fair_p - prev if prev is not None else None

            reasons = []
            if ev >= config.MIN_EDGE:
                reasons.append({"type": "value",
                                "text": f"{ev:.1%} better than the market's fair price"})
            if movement is not None and movement >= config.MOVE_THRESHOLD and ev >= 0:
                reasons.append({"type": "move",
                                "text": f"Win chance up {movement:.1%} since the last update"})
            if not reasons:
                continue
            if movement is not None and movement <= -config.MOVE_THRESHOLD:
                reasons.append({"type": "caution",
                                "text": f"Win chance down {-movement:.1%} since the last update"})

            score = confidence_score(ev, len(per_book), spread, movement)
            picks.append({
                "id": f"{g['event_id']}|{side}",
                "event_id": g["event_id"],
                "sport": sport,
                "side": side,
                "pick": team_for[side],
                "home_team": g["home_team"],
                "away_team": g["away_team"],
                "start_time_utc": g["start_time_utc"],
                "odds": best_price,
                "sportsbook": best_book,
                "fair_win_prob": round(fair_p, 4),
                "expected_value": round(ev, 4),
                "books": len(per_book),
                "line_movement": round(movement, 4) if movement is not None else None,
                "confidence": score,
                "rating": rating(score),
                "reasons": reasons,
                "three_way": "draw" in fair,   # soccer-style market where a draw is its own outcome
            })

    return picks, fair_by_event
