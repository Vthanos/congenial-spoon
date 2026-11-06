import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper import manual  # noqa: E402
from scraper.compare import mark_cheapest, match_key  # noqa: E402
from scraper.categorise import categorise  # noqa: E402
from scraper.lidl import parse_item, parse_unit_price  # noqa: E402
from scraper.run import enrich, update_history  # noqa: E402


def lidl_item(**data):
    base = {
        "havingPrice": True, "erpNumber": "1", "fullTitle": "Thing", "category": "Food",
        "canonicalUrl": "/p/thing/p1", "image": "x.png",
        "keyfacts": {"wonCategoryPrimary": "Worlds of need/Food and near food/Ready meals/Chilled ready-to-eat meals"},
        "price": {"price": 2.49},
    }
    base.update(data)
    return {"gridbox": {"data": base}}


class UnitPrice(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_unit_price("85p/kg"), (0.85, "kg"))
        self.assertEqual(parse_unit_price("£2.27/1kg"), (2.27, "kg"))
        self.assertEqual(parse_unit_price("£1.20/100g"), (12.0, "kg"))
        self.assertEqual(parse_unit_price("£1.35/l"), (1.35, "l"))
        self.assertEqual(parse_unit_price("Lidl Plus price £6.24/kg, Regular price £6.86/kg"), (6.24, "kg"))
        self.assertEqual(parse_unit_price("53p/kiwi"), (None, None))


class Categorise(unittest.TestCase):
    def test_cases(self):
        F = "Worlds of need/Food and near food/"
        cases = {
            ("Butternut Squash", F + "Fruit & vegetables/Vegetables"): ("Fruit & veg", "cook"),
            ("Conference Pears", F + "Fruit & vegetables/Fruit"): ("Fruit & veg", "no-cook"),
            ("BELBAKE Milk Chocolate Chips", F + "Food Cupboard/Baking ingredients"): ("Cupboard", "cook"),
            ("Choco Nussa Chocolate Spread", ""): ("Snacks & sweets", "no-cook"),
            ("Tesco Chicken Tikka Masala & Rice", ""): ("Ready meals", "heat-only"),
            ("Pepperoni Pizza", ""): ("Pizza & frozen", "heat-only"),
            ("Chicken & Bacon Sandwich", ""): ("Food to go", "no-cook"),
            ("Orange Juice 1L", ""): ("Drinks", "drink"),
            ("Beef Mince 5% Fat", ""): ("Meat & fish (raw)", "cook"),
            ("Tesco Finest Prawn Cocktail Handcooked Crisps 150g", ""): ("Snacks & sweets", "no-cook"),
            ("M&S Cotes Du Rhone Rose", ""): ("Alcohol", "drink"),
            ("Rosedene Farms Small Pear Pack 550G", ""): ("Fruit & veg", "no-cook"),
            ("M&S Beef Lasagne Serves 1", ""): ("Ready meals", "heat-only"),
        }
        for (name, path), want in cases.items():
            self.assertEqual(categorise(name, path), want, name)


class LidlParse(unittest.TestCase):
    def test_plain(self):
        p = parse_item(lidl_item())
        self.assertEqual((p["price"], p["was_price"], p["offer"]), (2.49, None, None))
        self.assertEqual(p["url"], "https://www.lidl.co.uk/p/thing/p1")

    def test_discount(self):
        p = parse_item(lidl_item(price={"price": 0.85, "oldPrice": 1.25,
                                        "discount": {"showDiscount": True, "percentageDiscount": 32}}))
        self.assertEqual((p["price"], p["was_price"], p["offer"]), (0.85, 1.25, "32% off"))

    def test_lidl_plus_save_amount(self):
        p = parse_item(lidl_item(price={}, lidlPlus=[{"price": {"price": 4.99}, "highlightText": "Save 50p"}]))
        self.assertEqual((p["price"], p["was_price"], p["loyalty"]), (4.99, 5.49, True))

    def test_lidl_plus_save_percent(self):
        p = parse_item(lidl_item(price={}, lidlPlus=[{"price": {"price": 0.32}, "highlightText": "Save 50%"}]))
        self.assertEqual(p["was_price"], 0.64)

    def test_multibuy_is_not_a_saving(self):
        p = parse_item(lidl_item(price={}, lidlPlus=[{"price": {"price": 3.50}, "highlightText": "2 FOR £7"}]))
        self.assertEqual((p["price"], p["was_price"], p["offer"]), (3.50, None, "2 FOR £7"))

    def test_skips_non_food(self):
        item = lidl_item(keyfacts={"wonCategoryPrimary": "Worlds of need/Baby, child & toys/Toys"})
        self.assertIsNone(parse_item(item))


class ManualAndRun(unittest.TestCase):
    def test_manual_csv(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "m.csv"
            path.write_text(
                "store,name,price,was_price,offer,loyalty,pack,unit_price,category,effort,valid_until,url\n"
                "Tesco,Tikka Masala,2.50,3.25,Clubcard Price,yes,400g,£6.25/kg,,,2999-01-01,\n"
                "Tesco,Expired thing,1,,,,,,,,2000-01-01,\n"
                "M&S,Meal deal,£5,,Meal deal,,,,Food to go,no-cook,,\n", encoding="utf-8")
            rows = manual.scrape(path)
        self.assertEqual([r["name"] for r in rows], ["Tikka Masala", "Meal deal"])
        t = enrich(rows[0])
        self.assertEqual((t["category"], t["saving"], t["saving_pct"], t["loyalty"]), ("Ready meals", 0.75, 23, True))
        m = enrich(rows[1])
        self.assertEqual((m["category"], m["effort"]), ("Food to go", "no-cook"))

    def test_history(self):
        p = {"id": "a", "price": 2.0}
        h = update_history([p], {"a": [["2026-11-01", 3.0]]}, "2026-11-06")
        self.assertEqual(h["a"], [["2026-11-01", 3.0], ["2026-11-06", 2.0]])
        self.assertTrue(p["is_lowest"])


class CompareShops(unittest.TestCase):
    def prod(self, store, name, price, unit_price=None, unit="kg", pack=None):
        return {"store": store, "name": name, "price": price, "pack": pack,
                "unit_price": unit_price, "unit": unit if unit_price else None}

    def test_match_key_ignores_shop_brand_and_size(self):
        self.assertEqual(match_key("Tesco British Chicken Breast Fillets 1KG"),
                         match_key("M&S British Chicken Breast Fillets"))
        self.assertEqual(match_key("Tesco Beef Lasagne 400G"), match_key("M&S Beef Lasagne Serves 1"))
        self.assertNotEqual(match_key("Tesco Beef Mince 20% Fat 500g"), match_key("M&S Beef Mince 5% Fat"))
        self.assertIsNone(match_key("M&S Spaghetti"))  # too vague to match safely

    def test_cheaper_shop_wins_on_unit_price(self):
        big = self.prod("Tesco", "Tesco Chicken Breast Fillets 2kg", 11.50, 5.75)
        small = self.prod("M&S", "M&S Chicken Breast Fillets", 5.50, 11.00)
        mark_cheapest([big, small])
        self.assertTrue(big["best_across_shops"])
        self.assertEqual(small["cheaper_at"]["store"], "Tesco")
        self.assertNotIn("cheaper_at", big)

    def test_same_shop_or_no_unit_is_left_alone(self):
        a = self.prod("Tesco", "Tesco Beef Lasagne 400G", 3.85, 9.62)
        b = self.prod("Tesco", "Tesco Beef Lasagne 800G", 6.00, 7.50)
        c = self.prod("M&S", "M&S Beef Lasagne", 4.20)  # no £/kg, no pack: can't compare
        mark_cheapest([a, b, c])
        self.assertFalse(any(k in p for p in (a, b, c) for k in ("cheaper_at", "best_across_shops")))

    def test_clean_offer(self):
        self.assertIsNone(manual.clean_offer("Important information"))
        self.assertEqual(manual.clean_offer("£5.50 Meal Deal Drink Clubcard Price £6 Meal Deal Drink Regular Price"),
                         "Meal deal drink (£5.50 deal with Clubcard)")


if __name__ == "__main__":
    unittest.main()
