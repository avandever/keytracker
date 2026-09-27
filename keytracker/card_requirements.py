"""Does a deck satisfy a week's required-card rule?

A week can require a named card, or a category of them. Both the endpoint that
enforces the rule on submission and the serialiser that shows a team what is
left to claim need the same answer, so the matching lives here rather than in
either of them.
"""

_CATEGORY_MATCH_FIELDS = (
    "traits",
    "card_types",
    "rarities",
    "expansions",
    "card_titles",
    "houses",
    "is_anomaly",
)


def _norm_card_title(title) -> str:
    """Compare card titles without tripping over the apostrophe.

    Card data uses a typographic apostrophe -- Alaka’s Brew -- so a list typed
    with a plain one would silently match nothing.
    """
    return (title or "").strip().lower().replace("’", "'").replace("ʼ", "'")


def _card_matches_category(card, category) -> bool:
    """Does one card in a deck satisfy one required-card category?

    Every match field the category sets must be satisfied, so rarities
    ["Special"] plus card_types ["Upgrade"] means a special upgrade rather than
    anything special or any upgrade. Within one field the values are
    alternatives. An empty category would match everything, so it never counts.
    """
    if not any(category.get(f) for f in _CATEGORY_MATCH_FIELDS):
        return False

    titles = {_norm_card_title(t) for t in category.get("card_titles") or []}
    if titles and _norm_card_title(card.card_title) not in titles:
        return False

    houses = {h.lower() for h in category.get("houses") or []}
    if houses and (card.natural_house or "").lower() not in houses:
        return False

    if category.get("is_anomaly") and not card.is_anomaly:
        return False

    traits = {t.lower() for t in category.get("traits") or []}
    if traits:
        card_traits = {(t.name or "").lower() for t in (card.traits or [])}
        if not (traits & card_traits):
            return False

    card_types = {t.lower() for t in category.get("card_types") or []}
    if card_types and (card.card_type or "").lower() not in card_types:
        return False

    rarities = {r.lower() for r in category.get("rarities") or []}
    if rarities and (card.rarity or "").lower() not in rarities:
        return False

    expansions = category.get("expansions") or []
    if expansions and card.expansion not in expansions:
        return False

    return True


def _deck_category_matches(deck, categories) -> dict:
    """Index of each category the deck satisfies -> the titles that satisfied it."""
    matches = {}
    for card in deck.cards_from_assoc or []:
        if not card.card_title:
            continue
        for index, category in enumerate(categories or []):
            if _card_matches_category(card, category):
                matches.setdefault(index, set()).add(card.card_title)
    return matches


def _qualifying_card_titles(deck, required_names, categories) -> set:
    """Titles of the deck's cards that satisfy the week's required-card rule.

    Names and categories form a single pool: a deck qualifies by containing any
    named card OR any card matching any category. That is what makes "a special
    rarity card" expressible -- several shapes of the same requirement rather
    than several separate requirements.
    """
    wanted = {_norm_card_title(n) for n in (required_names or [])}
    matched = {
        card.card_title
        for card in deck.cards_from_assoc or []
        if card.card_title and _norm_card_title(card.card_title) in wanted
    }
    for titles in _deck_category_matches(deck, categories).values():
        matched |= titles
    return matched


def _describe_category(category, index=None) -> str:
    """How one category should read in an error message."""
    label = (category.get("label") or "").strip()
    if label:
        return label
    bits = []
    if category.get("is_anomaly"):
        bits.append("an anomaly")
    for field in ("rarities", "traits", "houses", "card_types", "card_titles"):
        values = category.get(field) or []
        if values:
            bits.append("/".join(values[:3]) + ("..." if len(values) > 3 else ""))
    if bits:
        return " ".join(bits)
    return f"category {index + 1}" if index is not None else "a qualifying card"


def _describe_card_requirement(required_names, categories) -> str:
    """How the week's requirement should read in an error message."""
    parts = list(required_names or [])
    for index, category in enumerate(categories or []):
        parts.append(_describe_category(category, index))
    return ", ".join(parts)
