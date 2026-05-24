from pathlib import Path

MAX_PRINCIPLES_CHARS = 12000


def load_coaching_principles() -> str:
    root_dir = Path(__file__).resolve().parents[3]
    path = root_dir / "COACHING_PRINCIPLES.MD"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return (
            "Microstakes MTT doctrine: small pots - steal, big pots - value bet, "
            "strong aggression from passive players - respect."
        )
    return text[:MAX_PRINCIPLES_CHARS]
