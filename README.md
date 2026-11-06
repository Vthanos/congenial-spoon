# Scrappy: cheap, low-effort food finder

Checks supermarket prices every morning, sorts them by **how much cooking they need**
(No cook / Just heat / Cooking / Drinks), puts the **offers first**, and gives you a
shopping list with a running total. It costs **£0/month** to host.

## Two views

- **My shop**: the things you buy every week (beef mince, chicken, rice, potatoes,
  spaghetti, chopped tomatoes, onions, pizza, Red Bull, Diet Coke, beer, wine). Each
  shows the cheapest options first by £/kg or £/litre, plus one chip per shop with
  its best price; the cheapest shop gets a ★. Edit the list in `docs/favourites.json`
  (`match` = words to look for, `exclude` = words to skip).
- **All deals**: everything, by category, offers first. When two shops sell the
  same product (e.g. Tesco vs M&S chicken breast fillets), the cheaper one is marked
  "Cheapest shop" and the dearer one is hidden (untick *Hide items cheaper at another
  shop* to see both, with a "Cheaper at Tesco: £x/kg" note). Matching is done in
  `scraper/compare.py` and only compares like with like (£/kg vs £/kg).

## What each shop gives us (honest version)

| Shop  | How | Notes |
|-------|-----|-------|
| Lidl  | Automatic, daily | Uses the public JSON behind lidl.co.uk search. Includes Lidl Plus prices (marked yellow) and the weekly offers. **Lidl only lists its weekly specials online**, so everyday staples (mince, rice, Red Bull…) show "Lidl: not listed". Add Lidl prices you see in store to `data/manual_deals.csv`. |
| Tesco | **Snapshots** in `data/snapshots/tesco*.csv` | tesco.com blocks automated requests (HTTP 403), so prices are copied from a normal browser session. Last done 6 Nov 2026: 273 Clubcard offers (`tesco.csv`) + 125 regular prices for your staples (`tesco_staples.csv`). |
| M&S   | **Snapshots** in `data/snapshots/ms*.csv` | marksandspencer.com only sells cakes and party food online, so these are M&S products on Ocado (Ocado's prices, which can differ from M&S stores). Last done 6 Nov 2026: 128 offers + 46 staples. M&S doesn't sell Red Bull or Diet Coke under its own label. |

Snapshots don't update themselves. Rows expire automatically (Tesco by its own offer end date or after 2 weeks, M&S after 1 week), so stale prices vanish rather than mislead. Refresh them every week or two by browsing the offers pages again.

### Adding a Tesco / M&S deal yourself (takes 20 seconds)
On GitHub, open `data/manual_deals.csv`, click the pencil, add a line, and commit:

```
store,name,price,was_price,offer,loyalty,pack,unit_price,category,effort,valid_until,url
Tesco,Tesco Chicken Tikka Masala & Rice,2.50,3.25,Clubcard Price,yes,400g,£6.25/kg,,,2026-11-30,
```
Only `store`, `name` and `price` are required. Leave `category`/`effort` blank and they get guessed.
Expired deals (past `valid_until`) disappear automatically. If the same product is in a snapshot, your line wins.

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
- `scraper/manual.py`: your CSV deals + the Tesco/M&S snapshots (tidies their offer labels)
- `scraper/categorise.py`: category + effort level (edit the keyword lists to tweak it)
- `scraper/compare.py`: finds the same product at different shops and marks the cheaper one
- `scraper/run.py`: runs everything and keeps 120 days of price history, so it can flag
  "lowest we've seen" and spot fake offers. If a shop fails, yesterday's data is kept.
- `docs/`: the website (plain HTML/JS, no build step). The shopping list is saved on your phone.
  `docs/favourites.json` is your "My shop" list. If you change `style.css` or `app.js`,
  bump the `?v=` number in `index.html` so phones don't keep the old copy.

Be a good citizen: the scraper waits 1.5s between requests and runs once a day. Keep it that way.
