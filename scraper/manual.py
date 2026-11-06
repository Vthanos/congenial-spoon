"""Prices that don't come from a scraper.

- data/manual_deals.csv: deals you type in yourself (edit on GitHub, site rebuilds).
- data/snapshots/*.csv: Tesco and M&S (via Ocado) prices copied by browsing their
  sites, because both block automated price checks. These expire by themselves.
"""
import csv
import datetime as dt
import hashlib
import re
from pathlib import Path

from .lidl import parse_unit_price

DATA = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA / "manual_deals.csv"
SNAPSHOTS = DATA / "snapshots"  # deals copied from Tesco/Ocado by browsing (see README)


def _num(v):
    v = (v or "").strip().replace("£", "")
    if not v:
        return None
    if v.endswith("p"):
        return float(v[:-1]) / 100
    return float(v)


_NOT_OFFERS = {"important information", "everyday low price", "aldi price match"}
_PACK_JUNK = {"typically", "each"}


def clean_offer(text):
    """Shorten Tesco's wordy offer labels; drop labels that aren't offers."""
    text = (text or "").strip()
    if text.lower() in _NOT_OFFERS:
        return None
    m = re.match(r"(£[\d.]+) Meal Deal (Main|Snack|Drink) Clubcard Price", text)
    if m:
        return f"Meal deal {m.group(2).lower()} ({m.group(1)} deal with Clubcard)"
    return text or None


def scrape(path=None):
    """Your own deals first (they win on duplicates), then the browser snapshots."""
    paths = [path] if path else [CSV_PATH, *sorted(SNAPSHOTS.glob("*.csv"))]
    seen, out = set(), []
    for p in paths:
        for row in _read(p):
            if row["id"] not in seen:
                seen.add(row["id"])
                out.append(row)
    return out


def _read(path):
    if not path.exists():
        return []
    today = dt.date.today().isoformat()
    out = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            store = (row.get("store") or "").strip()
            if not name or not store or name.startswith("#"):
                continue
            valid_until = (row.get("valid_until") or "").strip() or None
            if valid_until and valid_until < today:
                continue  # expired deal
            price = _num(row.get("price"))
            if price is None:
                continue
            was = _num(row.get("was_price"))
            unit_text = (row.get("unit_price") or "").strip() or None
            unit_price, unit = parse_unit_price(unit_text)
            offer = clean_offer(row.get("offer"))
            pack = (row.get("pack") or "").strip()
            out.append({
                "id": "manual-" + hashlib.md5(f"{store}|{name}".lower().encode()).hexdigest()[:10],
                "store": store,
                "name": name,
                "price": round(price, 2),
                "was_price": round(was, 2) if was and was > price else None,
                "offer": offer,
                "loyalty": (row.get("loyalty") or "").strip().lower() in ("y", "yes", "true", "1"),
                "pack": None if pack.lower() in _PACK_JUNK else pack or None,
                "unit_text": unit_text,
                "unit_price": unit_price,
                "unit": unit,
                "store_category": "",
                "category_override": (row.get("category") or "").strip() or None,
                "effort_override": (row.get("effort") or "").strip() or None,
                "url": (row.get("url") or "").strip() or None,
                "image": None,
                "valid_until": valid_until,
                "manual": True,
            })
    return out
