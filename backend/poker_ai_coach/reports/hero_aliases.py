def hero_aliases(hero_name: str) -> list[str]:
    aliases = [hero_name.strip(), "hero"]
    unique_aliases = []
    seen = set()
    for alias in aliases:
        normalized = alias.lower()
        if alias and normalized not in seen:
            unique_aliases.append(alias)
            seen.add(normalized)
    return unique_aliases


def text_has_hero_alias(hand_text: str, hero_name: str) -> bool:
    lowered = hand_text.lower()
    return any(alias.lower() in lowered for alias in hero_aliases(hero_name))
