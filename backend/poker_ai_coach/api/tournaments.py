from fastapi import APIRouter, Query

from poker_ai_coach.config import get_settings
from poker_ai_coach.models.tournaments import TournamentHands, TournamentList
from poker_ai_coach.repositories.hm3_repository import get_tournament_hands, get_tournaments

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


@router.get("", response_model=TournamentList)
def tournament_list(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    search: str | None = Query(default=None),
    only_with_errors: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> TournamentList:
    return get_tournaments(
        settings=get_settings(),
        date_from=date_from,
        date_to=date_to,
        search=search,
        only_with_errors=only_with_errors,
        limit=limit,
    )


@router.get("/{tournament_number}/hands", response_model=TournamentHands)
def tournament_hands(
    tournament_number: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> TournamentHands:
    return get_tournament_hands(
        settings=get_settings(),
        tournament_number=tournament_number,
        limit=limit,
    )
