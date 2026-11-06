"""Run every source, categorise, track price history, write docs/data/*.json.

    python -m scraper.run
"""
import datetime as dt
import json
import sys
import traceback
from pathlib import Path

from . import lidl, manual
from .categorise import categorise
from .compare import mark_cheapest

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "data"
PRICES = OUT_DIR / "prices.json"
HISTORY = OUT_DIR / "history.json"
HISTORY_DAYS = 120

SOURCES = {"Lidl": lidl.scrape, "Manual": manual.scrape}


def _load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def enrich(p):
    cat, effort = categorise(p["name"], p.get("store_category"))
    p["category"] = p.pop("category_override", None) or cat
    p["effort"] = p.pop("effort_override", None) or effort
    if p.get("was_price"):
        p["saving"] = round(p["was_price"] - p["price"], 2)
        p["saving_pct"] = round(100 * p["saving"] / p["was_price"])
    else:
        p["saving"] = p["saving_pct"] = None
    p["on_offer"] = bool(p.get("offer") or p.get("was_price"))
    return p


def update_history(products, history, today):
    cutoff = (dt.date.fromisoformat(today) - dt.timedelta(days=HISTORY_DAYS)).isoformat()
    for p in products:
        h = [e for e in history.get(p["id"], []) if e[0] >= cutoff]
        if h and h[-1][0] == today:
            h[-1] = [today, p["price"]]
        elif not h or h[-1][1] != p["price"]:
            h.append([today, p["price"]])
        history[p["id"]] = h
        prices = [e[1] for e in h]
        p["lowest_recent"] = min(prices)
        p["is_lowest"] = len(h) > 1 and p["price"] <= min(prices)
    # forget products we haven't seen for a long time
    for k in [k for k, v in history.items() if not v or v[-1][0] < cutoff]:
        del history[k]
    return history


def main():
    today = dt.date.today().isoformat()
    previous = _load(PRICES, {"products": []})
    products, status = [], {}
    for name, fn in SOURCES.items():
        try:
            got = fn()
            status[name] = {"ok": True, "count": len(got)}
            products += got
            print(f"{name}: {len(got)} products")
        except Exception as e:  # keep yesterday's data rather than show nothing
            traceback.print_exc()
            old = [p for p in previous["products"] if p.get("source") == name]
            for p in old:
                p["stale"] = True
            products += old
            status[name] = {"ok": False, "count": len(old), "error": f"{type(e).__name__}: {e}"[:200]}
            print(f"{name}: FAILED ({e}); kept {len(old)} old products", file=sys.stderr)

    for p in products:
        p.setdefault("source", "Manual" if p.get("manual") else p["store"])
        enrich(p)
    mark_cheapest(products)
    history = update_history(products, _load(HISTORY, {}), today)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "sources": status,
        "products": sorted(products, key=lambda p: (p["category"], p["price"])),
    }
    PRICES.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    HISTORY.write_text(json.dumps(history, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(products)} products to {PRICES.relative_to(ROOT)}")
    if not any(s["ok"] and s["count"] for s in status.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
