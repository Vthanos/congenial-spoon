"""Lidl GB scraper using the public JSON behind lidl.co.uk's search page."""
import datetime as dt
import re
import urllib.error
import urllib.parse

from .http import get_json

BASE = "https://www.lidl.co.uk"
API = BASE + "/q/api/search"
PAGE_SIZE = 100
MAX_PER_TERM = 300

# Leans towards low-effort food, plus the staples you'd buy anyway.
SEARCH_TERMS = [
    "ready meal", "meal for two", "microwave", "pizza", "frozen", "soup", "noodles",
    "pasta", "rice", "pie", "sausage roll", "sandwich", "wrap", "salad", "hummus",
    "chicken", "ham", "tuna", "fish", "cheese", "yogurt", "milk", "eggs", "butter",
    "loaf", "rolls", "cereal", "porridge", "fruit", "banana", "vegetables", "potatoes",
    "beans", "crisps", "chocolate", "biscuits", "snack", "dessert", "juice", "coffee", "tea",
]


def _search(term):
    offset = 0
    while offset < MAX_PER_TERM:
        q = urllib.parse.urlencode({
            "q": term, "fetchsize": PAGE_SIZE, "offset": offset,
            "locale": "en_GB", "assortment": "GB", "version": "2.1.0",
        })
        data = get_json(f"{API}?{q}")
        items = data.get("items") or []
        for it in items:
            yield it
        offset += PAGE_SIZE
        if not items or offset >= data.get("numFound", 0):
            break


_UNIT_RX = re.compile(r"(£\s?(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s?p)\s*/\s*(\d+)?\s*(kg|g|l|litre|ml|cl)\b", re.I)


def parse_unit_price(text):
    """'85p/kg' -> (0.85, 'kg'); '£1.20/100g' -> (12.0, 'kg'); '£2/l' -> (2.0, 'l')."""
    if not text:
        return None, None
    m = _UNIT_RX.search(text)
    if not m:
        return None, None
    value = float(m.group(2)) if m.group(2) else float(m.group(3)) / 100
    qty = float(m.group(4) or 1)
    unit = m.group(5).lower()
    factor = {"kg": 1, "g": 1000, "l": 1, "litre": 1, "ml": 1000, "cl": 100}[unit]
    per = value / qty * factor
    return round(per, 2), ("kg" if unit in ("kg", "g") else "l")


def _money(text):
    m = re.search(r"£\s?(\d+(?:\.\d+)?)|(\d+)\s?p\b", text or "")
    if not m:
        return None
    return float(m.group(1)) if m.group(1) else int(m.group(2)) / 100


def _valid_until(g):
    for badge in (g.get("stockAvailability") or {}).get("badgeInfoV2") or []:
        ts = badge.get("validUntil")
        if ts:
            return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()
    return None


def parse_item(item):
    """Turn one raw API item into our common product dict (or None to skip)."""
    g = (item.get("gridbox") or {}).get("data") or {}
    if not g or not g.get("havingPrice"):
        return None
    path = (g.get("keyfacts") or {}).get("wonCategoryPrimary") or ""
    is_food = "Food and near food" in path or "Wine, beer" in path or (not path and g.get("category") == "Food")
    if not is_food or "/Household/" in path:
        return None  # skip the middle-aisle tents, drills and toilet roll

    p = g.get("price") or {}
    price = p.get("price")
    was = p.get("oldPrice") or (p.get("discount") or {}).get("deletedPrice")
    offer = None
    loyalty = False
    unit_text = (p.get("basePrice") or {}).get("text")
    pack = (p.get("packaging") or {}).get("text")

    lp = (g.get("lidlPlus") or [None])[0]
    if lp and (lp.get("price") or {}).get("price"):
        lpp = lp["price"]
        offer = lp.get("highlightText") or lp.get("lidlPlusText") or "Lidl Plus price"
        loyalty = True
        highlight = lp.get("highlightText") or ""
        # Only "Save 50p" / "Save 20%" tell us the regular price; "2 for £7" doesn't.
        regular = None
        if re.search(r"\bsave\b|\boff\b", highlight, re.I):
            pct = re.search(r"(\d+)\s?%", highlight)
            if pct:
                regular = round(lpp["price"] / (1 - int(pct.group(1)) / 100), 2)
            elif _money(highlight):
                regular = round(lpp["price"] + _money(highlight), 2)
        regular = price or regular
        price = lpp["price"]
        was = was or regular
        unit_text = (lpp.get("basePrice") or {}).get("text") or unit_text
        pack = (lpp.get("packaging") or {}).get("text") or pack
    elif (p.get("discount") or {}).get("showDiscount") and was:
        pct = p["discount"].get("percentageDiscount")
        offer = f"{pct}% off" if pct else "Reduced"

    if price is None:
        return None
    if was is not None and was <= price:
        was = None
    unit_price, unit = parse_unit_price(unit_text)

    return {
        "id": f"lidl-{g.get('erpNumber') or g.get('itemId')}",
        "store": "Lidl",
        "name": g.get("fullTitle") or g.get("title"),
        "price": round(price, 2),
        "was_price": round(was, 2) if was else None,
        "offer": offer,
        "loyalty": loyalty,
        "pack": pack,
        "unit_text": unit_text,
        "unit_price": unit_price,
        "unit": unit,
        "store_category": path,
        "url": BASE + (g.get("canonicalUrl") or ""),
        "image": g.get("image"),
        "valid_until": _valid_until(g) if offer else None,
    }


def scrape():
    seen, failed = {}, []
    for term in SEARCH_TERMS:
        try:
            for raw in _search(term):
                prod = parse_item(raw)
                if prod and prod["id"] not in seen:
                    seen[prod["id"]] = prod
        except Exception as e:  # one bad search shouldn't sink the run
            failed.append(term)
            print(f"  lidl: '{term}' failed: {type(e).__name__}: {e}")
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 429):
                print("  lidl: looks like we're being refused - stopping politely")
                break
    if not seen:
        raise RuntimeError(f"no Lidl products (failed terms: {failed})")
    print(f"  lidl: {len(seen)} products, {len(failed)} failed terms")
    return list(seen.values())
