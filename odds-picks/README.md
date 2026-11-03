# Picks Board

A personal sports betting dashboard for the NHL, NBA and NFL. It finds value bets
across moneylines, spreads and totals, lets you build your own singles and parlays,
and grades both its picks and your saved bets once games finish. It runs entirely on free
GitHub services, with no server to keep alive.

```
GitHub Actions (daily)                  GitHub Pages
  ├─ The Odds API: odds + final scores        └─ odds-picks/docs/index.html
  ├─ pipeline/  → finds and grades picks           reads docs/data/*.json
  └─ commits docs/data/*.json  ───────────────▶   (loads instantly)
```

## Set it up (about 10 minutes)

1. **Get an API key.** Sign up for the free plan at
   [the-odds-api.com](https://the-odds-api.com). The key arrives by email.
2. **Make a GitHub repo.** Create a new **public** repository (free GitHub Pages
   needs a public repo) and upload everything in this folder, including the hidden
   `.github` folder. With GitHub Desktop or `git push`, that happens automatically.
   If you upload in the browser, drag the folder contents in and check that
   `.github/workflows/update-picks.yml` is there.
3. **Add the key as a secret.** In the repo: Settings → Secrets and variables →
   Actions → New repository secret. Name it `ODDS_API_KEY` and paste the key.
   It stays private, even in a public repo.
4. **Turn on Pages.** Settings → Pages → Build and deployment → Source:
   **GitHub Actions**.
5. **Run it once.** Actions tab → Update picks → Run workflow. When it turns
   green (about a minute), your dashboard is live at
   `https://<your-username>.github.io/<repo-name>/`. Bookmark it, or use
   "Add to Home Screen" on your phone.

From then on it updates itself once a day, around 3 PM. The page shows sample data until
the first run finishes.

## Using it

On a computer, the Q and E keys switch between Picks, Build a bet and My bets.

- **Picks**: the featured pick is the highest-confidence one that hasn't started.
  Games drop off when they start. "Add to slip" puts a pick in your bet slip.
- **Build a bet**: every upcoming game with its spread, total and moneyline, at the
  best price across the sportsbooks checked. Tap prices to add them to the slip.
  Cyan percentages mark prices that beat the market's fair odds. With two or more
  picks you can switch between one parlay and separate singles, and the slip
  shows the payout, the parlay's fair chance of hitting, and its edge. Same-game
  legs are flagged, because sportsbooks price those parlays lower than straight
  multiplication. "Copy" puts the slip on your clipboard to enter at your sportsbook.
- **Your bets** (on the Picks tab) and **My bets**: bets you save from the slip, graded automatically from final scores,
  with your record and profit. They're stored in your browser, so each device
  keeps its own list.
- **Run an update** in the header opens the GitHub page with the "Run workflow"
  button, for when you want fresher odds than the schedule gives you.

## How picks are chosen

Every pick is still logged and graded in `docs/data/history.json` as a $10 paper bet,
so the model's track record can be checked there even though the page doesn't show it.

All the logic is in `pipeline/analyze.py`.

1. **Fair chance:** each sportsbook's odds include a margin. That is removed for
   every book, and the books are averaged into a consensus probability. Spreads and
   totals are compared at the line most books offer (say −1.5 or 6.5), so every
   price in the average is for the same bet.
2. **Value:** a pick needs a book whose price pays at least 2% more than that fair
   chance implies (positive expected value).
3. **Line move:** if a bet's fair chance moved 3+ points since the previous run,
   that can qualify it on its own, as long as the price is still fair. A move
   against a pick lowers its confidence.
4. **Confidence (0–100):** edge size (up to 50), number of books (up to 20), how
   closely the books agree (up to 15), and line movement (±15).

## Settings

Everything you'd want to change is in `pipeline/config.py`: sports, bet types,
thresholds, the $10 stake, and the credit safety floor. The update time is in
`.github/workflows/update-picks.yml`.

**API credits:** the free plan gives 500 a month. Each run costs 1 credit per bet
type per in-season sport (3 x 3 = 9), and checking final scores costs 2 per sport,
only when a game is waiting on a result. One run a day comes to roughly 400 a month.
A manual run costs about 9–15. Player props are priced one game at a time, so they'd
need a paid plan.
Off-season sports are skipped for free, and the pipeline stops spending at 25 left.
The page footer shows your remaining credits.

## Run it on your own computer

```
pip install -r requirements.txt
set ODDS_API_KEY=yourkey          # Mac/Linux: export ODDS_API_KEY=yourkey
python -m pipeline.update
python -m http.server -d docs     # then open http://localhost:8000
```

If you change classes in `docs/index.html`, rebuild the CSS with
`npx tailwindcss@3 -i styles/input.css -o docs/styles.css --minify`.
The workflow also rebuilds it on every run.

## Good to know

- **The data is public.** The dashboard and the files in `docs/data` can be seen
  by anyone who finds the URL (search engines are asked not to index it). Your API
  key is not.
- **GitHub may pause scheduled runs** in a repo with no activity for 60 days. If the
  page says the odds are more than a day old, open the Actions tab and re-enable
  the workflow.
- **Times** are shown in your device's time zone.

## Files

| Path | What it is |
| --- | --- |
| `pipeline/update.py` | One full run: fetch, analyze, log, grade, save |
| `pipeline/analyze.py` | Odds math and pick rules |
| `pipeline/grade.py` | Final scores and win/loss/push grading |
| `pipeline/odds_client.py` | The Odds API calls |
| `pipeline/config.py` | Settings |
| `docs/index.html` | The dashboard |
| `docs/data/picks.json` | Current picks (rewritten each run) |
| `docs/data/board.json` | Every upcoming game's prices, for Build a bet |
| `docs/data/scores.json` | Recent final scores, for grading |
| `docs/data/history.json` | Every pick ever made, with results |
| `docs/data/snapshots.json` | Last run's fair chances, for line movement |
| `.github/workflows/update-picks.yml` | The schedule |

Picks come from a statistical model and are not guarantees. 19+ in Ontario.
ConnexOntario: 1-866-531-2600.
