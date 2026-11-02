"""All the settings you're likely to want to change, in one place."""

from pathlib import Path

# Sports to check. Off-season sports are skipped automatically (free check).
# Full list of keys: https://the-odds-api.com/sports-odds-data/sports-apis.html
SPORTS = ["icehockey_nhl", "basketball_nba", "americanfootball_nfl"]

REGION = "us"             # bookmaker region: us, us2, uk, eu or au

# Bet types pulled for every game. Each one costs 1 credit per sport per run,
# so 3 markets x 3 sports = 9 credits a run. Player props aren't available
# here: they're priced per game and need a paid plan.
MARKETS = ["h2h", "spreads", "totals"]

# Pick rules
MIN_BOOKS = 3             # books needed for a reliable consensus
MIN_EDGE = 0.02           # 2% expected value to count as a value bet
MOVE_THRESHOLD = 0.03     # 3-point move in win probability between runs = significant

# Results tracking
STAKE = 10                # profit is shown as if you bet this much on every pick
GRADE_AFTER_HOURS = 4     # look for a final score this long after a game starts
SCORES_DAYS_BACK = 3      # how far back the scores lookup goes (max 3)
KEEP_SCORES_DAYS = 30     # final scores kept for grading bets saved in the browser

# Stop spending credits when the monthly allowance gets this low
CREDIT_FLOOR = 25

# Where the dashboard reads its data from
DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
