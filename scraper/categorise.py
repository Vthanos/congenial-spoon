"""Sort products into shopping categories and an 'effort' level.

effort:
  no-cook   - eat as it comes (sandwiches, fruit, yoghurt, cheese, bread, snacks)
  heat-only - microwave / oven / kettle, no real cooking (ready meals, pizza, soup, pouches)
  cook      - needs actual cooking (raw meat, dry pasta, flour...)
  drink     - drinks
"""
import re

# (category, effort, keyword regex) — checked in order, first match wins.
KEYWORD_RULES = [
    ("Alcohol", "drink", r"\b(wine|beer|lager|cider|gin|vodka|whisky|whiskey|rum|prosecco|champagne|ale|spirit|liqueur|sauvignon|chardonnay|pinot|malbec|merlot|shiraz|primitivo|gavi|burgundy|vinho|viognier|rioja|rhone|provence|puglia|cremant|brut|bucks fizz|cocktail can)\b|\bros[eé]\b"),
    ("Snacks & sweets", "no-cook", r"\bcrisps\b"),  # before "prawn cocktail", "chicken" etc.
    ("Ready meals", "heat-only", r"ready meal|meal for (one|two)|mini meal|serves (1|one)\b|main for (one|two)|& mash|and mash|kyivs?\b|arrabbiata|microwave|melt in the middle|en croute|fish cakes?|lasagne|cottage pie|shepherd'?s pie|fish pie|curry|tikka|korma|chow mein|risotto|mac(aroni)? (and|&|n) cheese|meatballs|al forno|moussaka|biryani|stir fry kit|rotolo"),
    ("Pizza & frozen", "heat-only", r"\bpizza|\bchips\b|fries|nuggets|fish fingers|potato waffles|hash brown|frozen|garlic bread|kiev|goujons|scampi|ice cream|tenders\b|breaded|tempura|prawn toast"),
    ("Soups, noodles & pots", "heat-only", r"\bsoup|noodle|pot\b|instant|pouch|microwave rice|rice pouch|steam bag|baked beans|spaghetti hoops|ravioli|tortelloni|gnocchi|filled pasta|fresh pasta"),
    ("Pies, rolls & bakes", "heat-only", r"sausage roll|pasty|pastie|\bpie\b|quiche|\bbake\b|spring rolls|samosa|bhaji|pakora|dim sum|gyoza"),
    ("Food to go", "no-cook", r"sandwich|\bwrap\b|sub\b|salad|sushi|pasta salad|snack pot|protein pot|hummus|houmous|dip\b|coleslaw|meal deal|antipasti"),
    ("Cooked meat & fish", "no-cook", r"\bham\b|cooked chicken|chicken (slices|pieces)|roast chicken|salami|mortadella|chorizo|pastrami|turkey slices|\bpate\b|smoked salmon|mackerel fillets|tuna|sardines|prawn cocktail|cooked prawns|cooked and peeled|prawn ring|scotch egg|pork pie"),
    ("Breakfast", "no-cook", r"cereal|granola|muesli|porridge|oats|cornflakes|bran|weetabix|wheat biscuits|croissant|pain au|brioche|cereal bar|breakfast"),
    ("Bakery", "no-cook", r"\bbread\b|loaf|sourdough|farmhouse|rolls\b|baguette|bagel|wraps|tortilla|pitta|naan|crumpet|muffin|teacake|scone|doughnut|donut|cake|pastry|pastries|cookies"),
    ("Drinks", "drink", r"juice|smoothie|\bwater\b|\bcola\b|lemonade|squash\b|coffee|\btea\b|teabags|energy drink|soft drink|fizzy|hot chocolate|oat drink|soya drink"),
    ("Snacks & sweets", "no-cook", r"crisps|chocolate|biscuit|sweets|popcorn|nuts|peanut|cashew|pretzel|crackers|rice cakes|flapjack|bar\b|dried fruit|raisins|mince pies|fruit gums|gummies|pigtails|percy pig|caterpillar|mini bites|fruit (twists|stars|strings|hearts)"),
    ("Dairy & eggs", "no-cook", r"milk|yogh?urt|cheese|cheddar|mozzarella|butter|spread|cream|eggs?\b|skyr|kefir|custard|rice pudding|dessert|trifle|mousse"),
    ("Fruit & veg", "no-cook", r"banana|apple|pear|orange|satsuma|clementine|easy peeler|grape|berr(y|ies)|melon|mango|pineapple|kiwi|avocado|tomato|cucumber|lettuce|salad leaves|carrot|pepper|plum|nectarine|peach|cherr(y|ies)|lemon|lime|stir fry|vegetable|veg\b|potato|onion|broccoli|squash|mushroom|cauliflower|spinach|parsnip|sprouts|cabbage|leek|courgette|sweetcorn|peas\b|fine beans|pomegranate|coriander|parsley"),
    ("Meat & fish (raw)", "cook", r"mince|steak|pancetta|chicken breast|chicken thigh|drumstick|whole chicken|pork|lamb|beef|sausages|bacon|gammon|burger|salmon fillet|cod|haddock|fish fillet|turkey|duck|venison"),
    ("Cupboard", "cook", r"pasta|spaghetti|penne|fusilli|rice\b|flour|sugar|oil\b|sauce|stock|tinned|chopped tomatoes|lentils|chickpeas|kidney beans|baking|yeast|spice|herbs|salt|vinegar|jam|honey|peanut butter|marmite|ketchup|mayonnaise|cooking"),
]
KEYWORD_RULES = [(c, e, re.compile(p, re.I)) for c, e, p in KEYWORD_RULES]

# Fallback on Lidl's own category path when the name gives nothing away.
LIDL_PATH_RULES = [
    ("Wine, beer", "Alcohol", "drink"),
    ("Ready meals/Salads", "Food to go", "no-cook"),
    ("Ready meals", "Ready meals", "heat-only"),
    ("Frozen Fish", "Meat & fish (raw)", "cook"),
    ("Frozen Meat", "Meat & fish (raw)", "cook"),
    ("Frozen Vegetables", "Fruit & veg", "cook"),
    ("Frozen", "Pizza & frozen", "heat-only"),
    ("Bakery", "Bakery", "no-cook"),
    ("Fruit & vegetables", "Fruit & veg", "no-cook"),
    ("Candy & Snacks", "Snacks & sweets", "no-cook"),
    ("Dairy", "Dairy & eggs", "no-cook"),
    ("Cheese", "Dairy & eggs", "no-cook"),
    ("Sausage", "Cooked meat & fish", "no-cook"),
    ("Meat", "Meat & fish (raw)", "cook"),
    ("Fish", "Meat & fish (raw)", "cook"),
    ("Beverages", "Drinks", "drink"),
    ("Drinks", "Drinks", "drink"),
    ("Coffee", "Drinks", "drink"),
    ("Breakfast", "Breakfast", "no-cook"),
    ("Food Cupboard", "Cupboard", "cook"),
]


# Store aisles that are reliable enough to trust over keywords
# (stops "butternut squash" being a drink or "chocolate chips" being frozen chips).
STRONG_PATH_RULES = [
    ("Fruit & vegetables", "Fruit & veg", "no-cook"),
    ("Baking ingredients", "Cupboard", "cook"),
    ("Candy & Snacks", "Snacks & sweets", "no-cook"),
    ("Bakery", "Bakery", "no-cook"),
    ("Wine, beer", "Alcohol", "drink"),
    ("Pickled", "Cupboard", "no-cook"),
    ("Frozen Pizza & Snacks", "Pizza & frozen", "heat-only"),
    ("Chilled ready-to-eat", "Ready meals", "heat-only"),
    ("Fresh Pasta", "Soups, noodles & pots", "heat-only"),
]
NEEDS_COOKING_VEG = re.compile(r"potato|onion|squash|parsnip|leek|cabbage|sprout|broccoli|cauliflower|swede|turnip|mushroom|courgette|aubergine|fine beans|frozen", re.I)


def categorise(name, store_category=""):
    """Return (category, effort) for a product."""
    category, effort = _categorise(name, store_category or "")
    if category == "Fruit & veg" and NEEDS_COOKING_VEG.search(name):
        effort = "cook"
    return category, effort


def _categorise(name, store_category):
    for needle, category, effort in STRONG_PATH_RULES:
        if needle.lower() in store_category.lower():
            return category, effort
    # Frozen raw meat/fish is still 'cook', and frozen veg stays veg — check the
    # store path for explicit raw-ingredient sections before keyword guessing.
    for category, effort, rx in KEYWORD_RULES:
        if rx.search(name):
            if category == "Pizza & frozen" and re.search(r"Frozen (Fish|Meat|Vegetables)", store_category):
                break  # e.g. "frozen cod fillets": let the path rules decide
            return category, effort
    for needle, category, effort in LIDL_PATH_RULES:
        if needle.lower() in store_category.lower():
            return category, effort
    return "Other", "cook"
