"""Spot the same product at different shops and flag which one is cheaper.

Two products "match" when their names are the same once shop names, own-brand
labels (Finest, Deluxe, Collection...) and pack sizes are stripped, e.g.
"Tesco British Chicken Breast Fillets 1KG" and "M&S British Chicken Breast Fillets".
They're only compared on £/kg or £/litre (or the same pack size), so a big pack
never "loses" to a small one just because the price tag is higher.
"""
import re
from collections import defaultdict

_BRANDS = re.compile(
    r"\b(tesco|lidl|m ?& ?s|marks (and|&) spencer|finest|collection|deluxe|chef select|"
    r"select farms|growers?'?s? harvest|hearty food co|stockwell|cook with|our best ever|"
    r"count on us|made in italy|british|outdoor bred)\b"
)
_SIZE = re.compile(
    r"\b\d+(\.\d+)?\s?(g|kg|ml|l|cl|ltr|litre|litres|pk|pack)\b"  # 500g, 1.5kg, 75cl
    r"|\b\d+\s?x\s?\d+(\.\d+)?\s?\w*"                            # 4 x 400g, 12x330ml
    r"|\bserves?\s?\d+\b"
)
_STOP = {"with", "and", "in", "a", "the", "of", "pack", "min", "minimum", "x"}


def match_key(name):
    s = (name or "").lower().replace("&", " & ")
    s = _BRANDS.sub(" ", s)
    s = _SIZE.sub(" ", s)
    words = {w for w in re.findall(r"[a-z]+|\d+%", s) if w not in _STOP}
    return " ".join(sorted(words)) if len(words) >= 2 else None


def _basis(p):
    """What we compare on: same unit (£/kg, £/l) or, failing that, identical pack."""
    if p.get("unit_price"):
        return p["unit"], p["unit_price"]
    if p.get("pack"):
        return "pack:" + p["pack"].lower().replace(" ", ""), p["price"]
    return None


def mark_cheapest(products):
    """Adds to each product that has a rival at another shop:
       best_across_shops=True                   on the cheapest one
       cheaper_at={store, price, unit_price...} on the dearer ones
    """
    groups = defaultdict(list)
    for p in products:
        p.pop("best_across_shops", None)
        p.pop("cheaper_at", None)
        key, basis = match_key(p["name"]), _basis(p)
        if key and basis:
            groups[(key, basis[0])].append((basis[1], p))

    for items in groups.values():
        if len({p["store"] for _, p in items}) < 2:
            continue  # only one shop sells it: nothing to compare
        best_value, best = min(items, key=lambda t: (t[0], t[1]["price"]))
        best["best_across_shops"] = True
        for value, p in items:
            if p["store"] != best["store"] and value > best_value:
                p["cheaper_at"] = {
                    "store": best["store"],
                    "name": best["name"],
                    "price": best["price"],
                    "unit_price": best.get("unit_price"),
                    "unit": best.get("unit"),
                    "loyalty": best.get("loyalty", False),
                }
    return products
