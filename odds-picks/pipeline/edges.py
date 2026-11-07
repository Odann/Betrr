"""
Arbitrage and middle finder, run across every book's offer on the board.

Arbitrage: at the same line, the best prices on each side come from
different books and their implied chances add to less than 100%, so a split
stake profits whatever happens.

Middle: two books disagree on the line (say Leafs -1.5 at one, Habs +2.5 at
another, or Over 6 and Under 7). Bet both sides; if the result lands between
the lines both bets win, and otherwise one wins and one loses, which usually
costs only a little.
"""


import math

from .analyze import american_to_decimal, fmt_point

STAKE = 100                  # stakes and payouts are shown for $100 on each side
MAX_MIDDLE_COST = 12         # skip middles that lose more than this on $200 if they miss


def _game_meta(g: dict) -> dict:
    return {"event_id": g["event_id"], "sport": g["sport"], "home_team": g["home_team"],
            "away_team": g["away_team"], "start_time_utc": g["start_time_utc"]}


def _label(market, key, point, g):
    if market == "totals":
        return f"{key.title()} {point:g}"
    team = {"home": g["home_team"], "away": g["away_team"], "draw": "Draw"}[key]
    return team if market == "h2h" else f"{team} {fmt_point(point)}"


def find_arbs(g: dict) -> list[dict]:
    out = []
    for market, m in g["markets"].items():
        lines = {}
        for o in m.get("offers", []):
            lines.setdefault(o["line"], []).append(o)
        for line, offers in lines.items():
            keys = sorted({k for o in offers for k in o["sides"]})
            best = {}
            for k in keys:
                cands = [(o["sides"][k][0], o["sides"][k][1], o["book"]) for o in offers if k in o["sides"]]
                best[k] = max(cands, key=lambda c: american_to_decimal(c[0]))
            if len(best) < 2 or len({b[2] for b in best.values()}) < 2:
                continue
            inv = sum(1 / american_to_decimal(b[0]) for b in best.values())
            if inv >= 1:
                continue
            total = STAKE * len(best)
            legs = [{"book": b[2], "label": _label(market, k, b[1], g), "price": b[0], "point": b[1],
                     "stake": round(total * (1 / american_to_decimal(b[0])) / inv, 2)}
                    for k, b in best.items()]
            out.append({**_game_meta(g), "kind": "arb", "market": market, "line": line,
                        "profit_pct": round(1 / inv - 1, 4), "total_stake": total, "legs": legs})
    return out


def find_middles(g: dict) -> list[dict]:
    out = []
    for market in ("spreads", "totals"):
        m = g["markets"].get(market)
        if not m:
            continue
        if market == "spreads":
            a_key, b_key = "home", "away"
        else:
            a_key, b_key = "over", "under"
        a_side = [(o["sides"][a_key][1], o["sides"][a_key][0], o["book"]) for o in m.get("offers", []) if a_key in o["sides"]]
        b_side = [(o["sides"][b_key][1], o["sides"][b_key][0], o["book"]) for o in m.get("offers", []) if b_key in o["sides"]]
        seen = set()
        for (pa, price_a, book_a) in a_side:
            for (pb, price_b, book_b) in b_side:
                if book_a == book_b:
                    continue
                if market == "spreads":
                    # home covers if margin > -pa; away covers if margin < pb  (margin = home - away)
                    lo, hi = -pa, pb
                else:
                    lo, hi = pa, pb            # over pa and under pb both win if pa < total < pb
                if math.floor(lo) + 1 >= hi:
                    continue        # no whole-number score lands strictly between the lines
                win_a, win_b = STAKE * (american_to_decimal(price_a) - 1), STAKE * (american_to_decimal(price_b) - 1)
                miss = round(min(win_a, win_b) - STAKE, 2)
                if -miss > MAX_MIDDLE_COST:
                    continue
                key = (pa, pb)
                if key in seen:
                    continue
                seen.add(key)
                out.append({**_game_meta(g), "kind": "middle", "market": market,
                            "window": [lo, hi], "if_hits": round(win_a + win_b, 2), "if_misses": miss,
                            "total_stake": 2 * STAKE,
                            "legs": [{"book": book_a, "label": _label(market, a_key, pa, g), "price": price_a, "point": pa, "stake": STAKE},
                                     {"book": book_b, "label": _label(market, b_key, pb, g), "price": price_b, "point": pb, "stake": STAKE}]})
    # keep the best few per game: widest window, then cheapest miss
    out.sort(key=lambda x: (-(x["window"][1] - x["window"][0]), -x["if_misses"]))
    return out[:3]


def find_edges(board: list[dict]) -> dict:
    arbs, middles = [], []
    for g in board:
        arbs += find_arbs(g)
        middles += find_middles(g)
    arbs.sort(key=lambda a: -a["profit_pct"])
    return {"arbs": arbs, "middles": middles}
