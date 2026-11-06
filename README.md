# Scrappy: cheap, low-effort food finder

Checks supermarket prices every morning, sorts them by **how much cooking they need**
(No cook / Just heat / Cooking / Drinks), puts the **offers first**, and gives you a
shopping list with a running total. It costs **£0/month** to host.

## What each shop gives us (honest version)

| Shop  | How | Notes |
|-------|-----|-------|
| Lidl  | Automatic, daily | Uses the public JSON behind lidl.co.uk search. Includes Lidl Plus prices (marked yellow) and the weekly offers. Lidl only lists its current range and offers online, not every product in store. |
| Tesco | **You add deals** in `data/manual_deals.csv` | tesco.com blocks automated requests (HTTP 403), and Scrappy doesn't try to get round that. |
| M&S   | **You add deals** in `data/manual_deals.csv` | marksandspencer.com only sells cakes and party food online. Everyday M&S food is sold through Ocado, which also blocks bots. |

### Adding a Tesco / M&S deal (takes 20 seconds)
On GitHub, open `data/manual_deals.csv`, click the pencil, add a line, and commit:

```
store,name,price,was_price,offer,loyalty,pack,unit_price,category,effort,valid_until,url
Tesco,Tesco Chicken Tikka Masala & Rice,2.50,3.25,Clubcard Price,yes,400g,£6.25/kg,,,2026-11-30,
```
Only `store`, `name` and `price` are required. Leave `category`/`effort` blank and they get guessed.
Expired deals (past `valid_until`) disappear automatically. Delete the two `EXAMPLE` lines once you've started.

## Hosting it for free (one-time, ~10 minutes)

1. Create a free account at github.com and make a **new public repository** called `scrappy`.
   (Private repos only get Pages on paid plans.)
2. In this folder:
   ```
   git init -b main
   git add .
   git commit -m "Scrappy"
   git remote add origin https://github.com/<your-username>/scrappy.git
   git push -u origin main
   ```
3. On GitHub, go to **Settings → Pages → Build and deployment**, choose *Deploy from a branch*,
   branch `main`, folder `/docs`, and save.
4. Go to **Actions → Update prices → Run workflow** to fill it with today's prices.
5. Your site is at `https://<your-username>.github.io/scrappy/`. Add it to your phone's home screen.

From then on, GitHub runs the scraper every morning at around 6:30 and the site updates itself.

> If the Actions log shows Lidl failing (some shops block cloud servers), run
> `.\update.ps1` on your own PC instead. It scrapes and pushes the results. You can schedule it
> with Windows Task Scheduler.

## Running it on your PC
Needs Python 3.10+ only (no packages to install).
```
python -m scraper.run                 # fetch prices -> docs/data/prices.json
python -m http.server -d docs 8000    # open http://localhost:8000
python -m unittest discover -s tests  # tests
```

## How it's put together
- `scraper/lidl.py`: Lidl search API → common product format (price, was-price, Lidl Plus, £/kg, offer end date)
- `scraper/manual.py`: your CSV deals
- `scraper/categorise.py`: category + effort level (edit the keyword lists to tweak it)
- `scraper/run.py`: runs everything and keeps 120 days of price history, so it can flag
  "lowest we've seen" and spot fake offers. If a shop fails, yesterday's data is kept.
- `docs/`: the website (plain HTML/JS, no build step). The shopping list is saved on your phone.

Be a good citizen: the scraper waits 1.5s between requests and runs once a day. Keep it that way.
