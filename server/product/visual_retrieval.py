"""Narrow recognized subjects before semantic ranking inside broad categories."""

from django.db.models import Q


SUBJECT_TITLE_PATTERNS: dict[str, tuple[str, ...]] = {
    "Book": (r"books?", r"novels?", r"textbooks?", r"paperbacks?", r"hardcovers?"),
    "Notebook": (r"notebooks?", r"journals?", r"notepads?", r"diaries"),
    "Laptop": (r"laptops?", r"macbooks?", r"notebook\s+computers?"),
    "Computer monitor": (r"monitors?", r"computer\s+displays?"),
    "Keyboard": (r"keyboards?",),
    "Phone": (r"phones?", r"iphones?", r"smartphones?", r"galaxy"),
    "Headphones": (
        r"headphones?",
        r"earbuds?",
        r"earphones?",
        r"headsets?",
        r"airpods?",
    ),
    "Camera": (r"cameras?", r"dslr", r"mirrorless"),
    "Speaker": (r"speakers?", r"soundbars?"),
    "Shirt": (r"shirts?", r"t[ -]?shirts?", r"tees?", r"polos?", r"blouses?"),
    "Jacket": (
        r"jackets?",
        r"coats?",
        r"parkas?",
        r"anoraks?",
        r"blazers?",
        r"windbreakers?",
        r"puffers?",
    ),
    "Suit jacket / blazer": (
        r"blazers?",
        r"suits?",
        r"sports?\s+coats?",
        r"tailored\s+jackets?",
    ),
    "Trousers": (
        r"trousers?",
        r"pants",
        r"jeans",
        r"leggings?",
        r"chinos?",
        r"joggers?",
    ),
    "Dress": (r"dresses", r"dress", r"skirts?", r"gowns?"),
    "Shoes": (
        r"shoes?",
        r"sneakers?",
        r"trainers?",
        r"boots?",
        r"loafers?",
        r"oxfords?",
        r"derb(?:y|ies)",
        r"brogues?",
        r"sandals?",
        r"slippers?",
        r"moccasins?",
        r"footwear",
        r"heels?",
        r"pumps?",
        r"flats?",
        r"clogs?",
        r"cleats?",
        r"espadrilles?",
    ),
    "Bag": (r"bags?", r"handbags?", r"backpacks?", r"totes?", r"satchels?", r"purses?"),
    "Watch": (r"watches", r"watch", r"wristwatches", r"wristwatch", r"timepieces?"),
    "Jewelry": (
        r"jewel(?:ry|lery)",
        r"necklaces?",
        r"earrings?",
        r"bracelets?",
        r"rings?",
        r"pendants?",
        r"brooches",
    ),
    "Chair": (r"chairs?", r"stools?", r"recliners?", r"armchairs?"),
    "Table": (r"tables?", r"desks?", r"workstations?"),
    "Sofa": (r"sofas?", r"couches", r"couch", r"loveseats?", r"sectionals?"),
    "Lamp": (r"lamps?", r"lights?", r"lighting", r"lanterns?"),
    "Vase": (r"vases?",),
    "Exercise equipment": (
        r"dumbbells?",
        r"barbells?",
        r"kettlebells?",
        r"treadmills?",
        r"exercise",
        r"resistance",
        r"weights?",
        r"fitness",
        r"yoga",
    ),
    "Toy": (r"toys?", r"puzzles?", r"dolls?", r"games?", r"blocks", r"lego", r"plush"),
    "Kitchen utensil": (
        r"utensils?",
        r"cookware",
        r"pans?",
        r"pots?",
        r"knives",
        r"knife",
        r"spatulas?",
        r"cutlery",
        r"kettles?",
        r"spoons?",
        r"forks?",
    ),
    "Beauty product": (
        r"beauty",
        r"skincare",
        r"serums?",
        r"creams?",
        r"makeup",
        r"lipsticks?",
        r"cleansers?",
        r"moisturi[sz]ers?",
        r"sunscreen",
    ),
    "Plant": (r"plants?", r"flowers?", r"succulents?", r"seedlings?"),
    "Pet supplies": (
        r"pets?",
        r"dogs?",
        r"cats?",
        r"pupp(?:y|ies)",
        r"kittens?",
        r"leashes?",
        r"litter",
        r"kibble",
    ),
    "Food or drink": (
        r"food",
        r"drinks?",
        r"coffee",
        r"tea",
        r"juices?",
        r"beverages?",
        r"snacks?",
        r"chocolate",
        r"water",
        r"soda",
    ),
}


SUBJECT_TITLE_EXCLUSIONS: dict[str, str] = {
    "Shoes": r"(^|[^a-z])(?:shoes?|boots?|sneakers?|footwear)[ -]+(?:racks?|polish|care|cleaners?|bags?|boxes|box|storage|trees?|horns?|laces?|insoles?|inserts?|covers?)([^a-z]|$)",
    "Dress": r"(^|[^a-z])dress[ -]+(?:shoes?|boots?|shirts?|socks?)([^a-z]|$)",
    "Watch": r"(^|[^a-z])(?:watches|watch|wristwatch)[ -]+(?:bands?|straps?|boxes|box|winders?|chargers?|stands?)([^a-z]|$)",
}


def subject_title_filter(label: str) -> Q:
    """Unknown subject labels fail closed instead of falling back to a category."""
    criteria = Q(pk__in=[])
    for term in SUBJECT_TITLE_PATTERNS.get(label, ()):
        criteria |= Q(title__iregex=rf"(^|[^a-z])(?:{term})([^a-z]|$)")
    if label in SUBJECT_TITLE_EXCLUSIONS:
        criteria &= ~Q(title__iregex=SUBJECT_TITLE_EXCLUSIONS[label])
    return criteria
