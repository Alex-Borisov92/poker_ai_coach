from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from poker_ai_coach.api import coach, database, hands, health, reports, study, tournaments, training

LOCAL_FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def create_app() -> FastAPI:
    app = FastAPI(title="Poker AI Coach", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_FRONTEND_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(database.router)
    app.include_router(reports.router)
    app.include_router(hands.router)
    app.include_router(coach.router)
    app.include_router(study.router)
    app.include_router(tournaments.router)
    app.include_router(training.router)
    return app


app = create_app()
