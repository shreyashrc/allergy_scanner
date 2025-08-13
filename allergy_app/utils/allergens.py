from __future__ import annotations

import re
import difflib
from typing import Dict, List, Optional, Set, Tuple


ALLERGEN_KEYWORDS: Dict[str, List[str]] = {
    "nuts": [
        "almond",
        "cashew",
        "hazelnut",
        "macadamia",
        "peanut",
        "pecan",
        "pistachio",
        "walnut",
        "nut",
        "praline",
        "marzipan",
        "nougat",
    ],
    "dairy": [
        "milk",
        "butter",
        "cheese",
        "cream",
        "yogurt",
        "lactose",
        "whey",
        "casein",
        "ghee",
        "yoghurt",
        "dairy",
        "lactate",
        "lactalbumin",
    ],
    "gluten": [
        "wheat",
        "barley",
        "rye",
        "oats",
        "flour",
        "bread",
        "pasta",
        "cereal",
        "gluten",
        "semolina",
        "spelt",
        "kamut",
        "bulgur",
        "couscous",
    ],
    "eggs": [
        "egg",
        "albumin",
        "albumen",
        "globulin",
        "lecithin",
        "livetin",
        "lysozyme",
        "mayonnaise",
        "meringue",
        "ovalbumin",
        "ovomucin",
    ],
    "soy": [
        "soy",
        "soya",
        "soybean",
        "tofu",
        "tempeh",
        "miso",
        "edamame",
        "shoyu",
        "tamari",
        "textured vegetable protein",
    ],
    "shellfish": [
        "shrimp",
        "crab",
        "lobster",
        "crayfish",
        "prawn",
        "scampi",
        "shellfish",
        "crustacean",
        "mollusc",
        "oyster",
        "clam",
        "mussel",
    ],
    "fish": [
        "fish",
        "anchovy",
        "bass",
        "cod",
        "flounder",
        "haddock",
        "halibut",
        "herring",
        "mackerel",
        "salmon",
        "sardine",
        "tuna",
        "tilapia",
    ],
    "sesame": ["sesame", "tahini", "sesamol", "gingelly", "benne"],
    "sulfites": [
        "sulfite",
        "sulphite",
        "sulfur dioxide",
        "sulphur dioxide",
        "metabisulfite",
        "metabisulphite",
    ],
    "mustard": ["mustard", "senf", "moutarde"],
}


def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.lower().split())


def _build_keyword_patterns() -> Dict[str, List[str]]:
    patterns: Dict[str, List[str]] = {}
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        compiled: List[str] = []
        for kw in keywords:
            escaped = "".join(["\\" + c if c in ".^$*+?{}[]|()" else c for c in kw])
            compiled.append(rf"\b{escaped}\b")
        patterns[allergen] = compiled
    return patterns


KEYWORD_PATTERNS: Dict[str, List[str]] = _build_keyword_patterns()


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _ngram(tokens: List[str], n: int) -> List[str]:
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def fuzzy_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def detect_allergens(ingredients_text: Optional[str]) -> Tuple[Set[str], Set[str], Dict[str, float]]:
    text = _normalize_text(ingredients_text)
    if not text:
        return set(), set(), {}

    direct_matches: Set[str] = set()
    may_contain_matches: Set[str] = set()
    allergen_confidence: Dict[str, float] = {}

    for allergen, patterns in KEYWORD_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                direct_matches.add(allergen)
                allergen_confidence[allergen] = max(allergen_confidence.get(allergen, 0.0), 1.0)
                break

    may_contain_indices = []
    start = 0
    needle = "may contain"
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            break
        may_contain_indices.append(idx)
        start = idx + len(needle)

    window_after = 80
    for idx in may_contain_indices:
        window = text[idx : idx + len(needle) + window_after]
        for allergen, patterns in KEYWORD_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, window, flags=re.IGNORECASE):
                    may_contain_matches.add(allergen)
                    allergen_confidence[allergen] = max(allergen_confidence.get(allergen, 0.0), 0.9)
                    break

    tokens = _tokenize(text)
    grams = set(tokens + _ngram(tokens, 2) + _ngram(tokens, 3))
    FUZZY_THRESHOLD = 0.85
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        for kw in keywords:
            for gram in grams:
                score = fuzzy_ratio(kw, gram)
                if score >= FUZZY_THRESHOLD:
                    direct_matches.add(allergen)
                    allergen_confidence[allergen] = max(allergen_confidence.get(allergen, 0.0), float(score))
                    break

    return direct_matches, may_contain_matches, allergen_confidence


def compute_risk_level(user_allergens, direct: Set[str], may_contain: Set[str], confidences: Optional[Dict[str, float]] = None):
    user_set = {a.lower() for a in (user_allergens or [])}
    direct_only = direct - may_contain
    if confidences is None:
        confidences = {}
    direct_hit = sorted([a for a in user_set.intersection(direct_only) if confidences.get(a, 1.0) >= 0.85])
    if direct_hit:
        from allergy_app.db.tables import RiskLevel
        return RiskLevel.DANGER, direct_hit
    warning_hit = sorted([a for a in user_set.intersection(may_contain) if confidences.get(a, 0.9) >= 0.85])
    if warning_hit:
        from allergy_app.db.tables import RiskLevel
        return RiskLevel.WARNING, warning_hit
    from allergy_app.db.tables import RiskLevel
    return RiskLevel.SAFE, []

