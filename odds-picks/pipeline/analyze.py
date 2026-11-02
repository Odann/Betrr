"""
Prices every game's main bets and finds picks among them.

For each market (moneyline, spread, total) on each game:
1. Main line: spreads and totals are compared at the line most books offer
   (e.g. -1.5 or 6.5), so every price in the average is for the same bet.
2. Fair chance: strip each book's margin (the "vig") so its outcomes add to
   100%, then average across books.
3. Value: the best price available pays more than the fair chance says it
   should:  EV = fair_chance * decimal_odds - 1  >=  MIN_EDGE
4. Line move: the fair chance moved MOVE_THRESHOLD or more since the last run.
   A move toward a side can qualify it on its own (if the price still isn't a
   losing bet); a move against a pick lowers its confidence.
5. Confidence (0-100): edge size, number of books, how closely they agree,
   and line movement.
"""

from collections import Counter
from statistics import mean, pstdev

from . import config

MARKET_LABELS = {"h2h": "Moneyline", "spreads": "Spread", "totals": "Total"}


def american_to_prob(price: int) -> float:
    return 100 / (price + 100) if price > 0 else -price / (-price + 100)


def american_to_decimal(price: int) -> float:
    return 1 + price / 100 if price > 0 else 1 + 100 / -price


def fmt_point(p: float) -> str:
    return "PK" if p == 0 else f"{p:+g}"


def confidence_score(ev: float, n_books: int, spread: float, movement: float | None) -> int:
    score = min(max(ev, 0) / 0.08, 1) * 50          # up to 50: edge size (maxes at 8%)
    score += min(n_books / 8, 1) * 20                # up to 20: number of books (maxes at 8)
    score += (1 - min(spread / 0.04, 1)) * 15        # up to 15: books agree with each other
    if movement is not None and abs(movement) >= config.MOVE_THRESHOLD:
        score += 15 if movement > 0 else -15         # +/-15: line moving with or against
    return round(max(0, min(100, score)))


def rating(score: int) -> str:
    return "High" if score >= 70 else "Medium" if score >= 45 else "Low"


def _book_sides(market: str, book: dict, home: str, away: str) -> tuple[object, dict] | None:
    """One book's offer as (line, {selection_key: (price, point)}), or None if incomplete."""
    sides = {}
    for o in book["outcomes"]:
        if market == "totals":
            key = o["name"].lower()                        # over / under
        elif o["name"] == home:
            key = "home"
        elif o["name"] == away:
            key = "away"
        elif o["name"] == "Draw":
            key = "draw"
        else:
            continue
        if market != "h2h" and o.get("point") is None:
            continue
        sides[key] = (o["price"], o.get("point"))

    if market == "h2h":
        return (None, sides) if {"home", "away"} <= sides.keys() else None
    if market == "spreads":
        return (sides["home"][1], sides) if {"home", "away"} <= sides.keys() else None
    if market == "totals":
        return (sides["over"][1], sides) if {"over", "under"} <= sides.keys() else None
    return None


def _label(market: str, key: str, point, home: str, away: str) -> str:
    if market == "totals":
        return f"{key.title()} {point:g}"
    team = {"home": home, "away": away, "draw": "Draw"}[key]
    return f"{team} {fmt_point(point)}" if market == "spreads" else team


def price_market(market: str, offers: list[dict], home: str, away: str) -> dict | None:
    """Main line for one market: best price, fair chance and edge per selection."""
    parsed = [(b["bookmaker"], s) for b in offers if (s := _book_sides(market, b, home, away))]
    if not parsed:
        return None
    line = Counter(s[0] for _, s in parsed).most_common(1)[0][0]
    at_line = [(book, sides) for book, (l, sides) in parsed if l == line]

    # Each book's margin-free chances
    per_book = []
    for _, sides in at_line:
        raw = {k: american_to_prob(price) for k, (price, _) in sides.items()}
        total = sum(raw.values())
        per_book.append({k: p / total for k, p in raw.items()})

    keys = [k for k in ("away", "home", "draw", "over", "under") if any(k in s for _, s in at_line)]
    selections = []
    for key in keys:
        prices = [(sides[key][0], sides[key][1], book) for book, sides in at_line if key in sides]
        best_price, point, best_book = max(prices, key=lambda x: american_to_decimal(x[0]))
        probs = [b[key] for b in per_book if key in b]
        fair = mean(probs) if len(probs) >= 2 else None
        selections.append({
            "key": key,
            "label": _label(market, key, point, home, away),
            "point": point,
            "odds": best_price,
            "book": best_book,
            "fair_prob": round(fair, 4) if fair is not None else None,
            "ev": round(fair * american_to_decimal(best_price) - 1, 4) if fair is not None else None,
            "agreement": pstdev(probs) if len(probs) >= 2 else None,
        })
    return {"line": line, "books": len(at_line), "selections": selections}


def analyze_games(games: list[dict], sport: str, previous_fair: dict) -> tuple[list, dict, list]:
    """
    Returns (picks, fair_by_key, board).
    previous_fair is {"event|market|selection|point": chance} from the last run.
    board is every game with its priced main bets, for the bet builder.
    """
    picks, fair_by_key, board = [], {}, []

    for g in games:
        markets = {}
        for market in config.MARKETS:
            priced = price_market(market, g["markets"].get(market, []), g["home_team"], g["away_team"])
            if not priced:
                continue
            for sel in priced["selections"]:
                agreement = sel.pop("agreement")
                if sel["fair_prob"] is None:
                    continue
                move_key = f"{g['event_id']}|{market}|{sel['key']}|{sel['point']}"
                fair_by_key[move_key] = sel["fair_prob"]
                prev = previous_fair.get(move_key)
                movement = sel["fair_prob"] - prev if isinstance(prev, (int, float)) else None
                ev = sel["ev"]

                if priced["books"] < config.MIN_BOOKS:
                    continue
                reasons = []
                if ev >= config.MIN_EDGE:
                    reasons.append({"type": "value", "text": f"{ev:.1%} better than the market's fair price"})
                if movement is not None and movement >= config.MOVE_THRESHOLD and ev >= 0:
                    reasons.append({"type": "move", "text": f"Fair chance up {movement:.1%} since the last update"})
                if not reasons:
                    continue
                if movement is not None and movement <= -config.MOVE_THRESHOLD:
                    reasons.append({"type": "caution", "text": f"Fair chance down {-movement:.1%} since the last update"})

                score = confidence_score(ev, priced["books"], agreement or 0, movement)
                picks.append({
                    "id": f"{g['event_id']}|{market}|{sel['key']}",
                    "event_id": g["event_id"],
                    "sport": sport,
                    "market": market,
                    "market_label": MARKET_LABELS[market],
                    "side": sel["key"],
                    "point": sel["point"],
                    "pick": sel["label"],
                    "home_team": g["home_team"],
                    "away_team": g["away_team"],
                    "start_time_utc": g["start_time_utc"],
                    "odds": sel["odds"],
                    "sportsbook": sel["book"],
                    "fair_win_prob": sel["fair_prob"],
                    "expected_value": ev,
                    "books": priced["books"],
                    "line_movement": round(movement, 4) if movement is not None else None,
                    "confidence": score,
                    "rating": rating(score),
                    "reasons": reasons,
                    "three_way": market == "h2h" and any(s["key"] == "draw" for s in priced["selections"]),
                })
            markets[market] = priced

        if markets:
            board.append({
                "event_id": g["event_id"], "sport": sport,
                "home_team": g["home_team"], "away_team": g["away_team"],
                "start_time_utc": g["start_time_utc"], "markets": markets,
            })

    return picks, fair_by_key, board
