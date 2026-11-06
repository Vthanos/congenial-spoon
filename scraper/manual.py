"""Deals you type in yourself (Tesco, M&S, anywhere) via data/manual_deals.csv.

Tesco and M&S block automated price checks (Tesco's site returns 403 to bots and
M&S everyday food is sold through Ocado, which does the same), so these come in
by hand. Edit the CSV on GitHub in the browser and the site rebuilds itself.
"""
import csv
import datetime as dt
import hashlib
from pathlib import Path

from .lidl import parse_unit_price

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "manual_deals.csv"


def _num(v):
    v = (v or "").strip().replace("£", "")
    if not v:
        return None
    if v.endswith("p"):
        return float(v[:-1]) / 100
    return float(v)


def scrape(path=CSV_PATH):
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
            offer = (row.get("offer") or "").strip() or None
            out.append({
                "id": "manual-" + hashlib.md5(f"{store}|{name}".lower().encode()).hexdigest()[:10],
                "store": store,
                "name": name,
                "price": round(price, 2),
                "was_price": round(was, 2) if was and was > price else None,
                "offer": offer,
                "loyalty": (row.get("loyalty") or "").strip().lower() in ("y", "yes", "true", "1"),
                "pack": (row.get("pack") or "").strip() or None,
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
