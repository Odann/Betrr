# Picks Board

A personal sports betting dashboard that finds moneyline value bets, tracks line
movement, and grades its own picks once games finish. It runs entirely on free
GitHub services, with no server to keep alive.

```
GitHub Actions (3x a day)                  GitHub Pages
  ├─ The Odds API: odds + final scores        └─ docs/index.html
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

From then on it updates itself three times a day. The page shows sample data until
the first run finishes.

## Using it

- **Featured pick** is the highest-confidence pick that hasn't started yet. Games
  drop off the board when they start.
- **Run an update** in the header opens the GitHub page with the "Run workflow"
  button, for when you want fresher odds than the schedule gives you.
- **How the picks have done** grades every pick as a flat $10 bet at the odds shown
  when it first appeared. The breakdown by High/Medium/Low is the honest test of
  whether the confidence rating means anything. Expect a few hundred picks before
  it does.

## How picks are chosen

All the logic is in `pipeline/analyze.py`.

1. **Fair win chance:** each sportsbook's odds include a margin. That is removed for
   every book, and the books are averaged into a consensus probability.
2. **Value:** a pick needs a book whose price pays at least 2% more than that fair
   chance implies (positive expected value).
3. **Line move:** if a team's win chance moved 3+ points since the previous run,
   that can qualify it on its own, as long as the price is still fair. A move
   against a pick lowers its confidence.
4. **Confidence (0–100):** edge size (up to 50), number of books (up to 20), how
   closely the books agree (up to 15), and line movement (±15).

## Settings

Everything you'd want to change is in `pipeline/config.py`: sports, thresholds,
the $10 stake, and the credit safety floor. The update times are in
`.github/workflows/update-picks.yml`.

**API credits:** the free plan gives 500 a month. Each run costs 1 credit per
in-season sport, and checking results costs 2 per sport, only when a pick is waiting
on a result. Three sports at three runs a day comes to roughly 300–450 a month.
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
| `pipeline/grade.py` | Win/loss grading from final scores |
| `pipeline/odds_client.py` | The Odds API calls |
| `pipeline/config.py` | Settings |
| `docs/index.html` | The dashboard |
| `docs/data/picks.json` | Current picks (rewritten each run) |
| `docs/data/history.json` | Every pick ever made, with results |
| `docs/data/snapshots.json` | Last run's fair odds, for line movement |
| `.github/workflows/update-picks.yml` | The schedule |

Picks come from a statistical model and are not guarantees. 19+ in Ontario.
ConnexOntario: 1-866-531-2600.
