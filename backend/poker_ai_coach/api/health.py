from fastapi import APIRouter

from poker_ai_coach import __version__
from poker_ai_coach.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "app": "poker-ai-coach",
        "version": __version__,
        "hero_name": settings.hero_name,
        "ai_enabled": settings.ai_enabled,
        "ai_configured": settings.ai_enabled and bool(settings.openai_api_key),
        "ai_model": settings.openai_model,
    }
