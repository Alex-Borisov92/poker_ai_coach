# DEVELOPMENT.md

## Purpose

This file defines how to build poker-ai-coach safely and in small steps.

Main rule:

- Start with local read-only HM3 database introspection.
- Then build reports.
- Then build hand review.
- Only then add AI coach features.

Do not start with full AI automation before reports and hand review are working.

## Local Setup

Create a virtual environment:

python -m venv .venv
.\.venv\Scripts\Activate.ps1

Install backend dependencies:

pip install -e ".[dev]"

Create .env from .env.example:

Copy-Item .env.example .env

Example .env:

HM3_DB_PATH=C:\Users\aleks\Desktop\pokerdom.hmdb
HERO_NAME=surok_valera
AI_ENABLED=false
OPENAI_API_KEY=
OPENAI_MODEL=
APP_HOST=127.0.0.1
APP_PORT=8000

Run backend:

uvicorn poker_ai_coach.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

Run frontend:

cd frontend
npm install
npm run dev

## Environment Variables

Required for DB reports:

HM3_DB_PATH=
HERO_NAME=surok_valera

Required for AI features:

AI_ENABLED=true
OPENAI_API_KEY=
OPENAI_MODEL=

If AI is disabled or no key exists, the app must still work with reports.

## Backend Development

Backend package lives in:

backend/poker_ai_coach/

Use FastAPI routes only as thin API layers.

Business logic should live in:

- db/
- repositories/
- reports/
- coach/

Routes should not contain complex SQL or report logic.

## Read-only SQLite Rules

Always open HM3 SQLite in read-only mode.

Use:

file:<absolute_path>?mode=ro

Do not modify the database.

Do not run unsafe SQL.

Blocked SQL statements:

- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- CREATE
- VACUUM
- ATTACH

Tests must use small synthetic SQLite fixture databases.

Never use the real user .hmdb file in tests.

## Frontend Development

Frontend lives in:

frontend/

Use React + TypeScript + Vite.

Main app pages:

- Overview
- Leak Finder
- Hand Review
- Tournaments
- Study Plan
- Coach Chat
- Settings

Use an app shell:

- left sidebar
- main content
- optional right coach panel

Do not build a marketing landing page.

The first screen should be useful immediately.

## UI Design Rules

Use a quiet analysis dashboard style.

Prefer:

- compact tables
- stat cards
- filters
- hand text viewer
- coach panel
- clear empty states
- clear warning states

Avoid:

- decorative hero sections
- gradient orb backgrounds
- marketing copy
- card-inside-card layouts
- oversized headings inside compact panels
- fake metrics

## Milestone 1 - DB Introspection

Goal:

Make the app open a local HM3 database in read-only mode and show database status.

Backend tasks:

1. Add FastAPI app.
2. Add health endpoint:
   GET /api/health
3. Add config loader.
4. Add read-only HM3 connection helper.
5. Add schema probe service.
6. Add endpoint:
   GET /api/database/status
7. Add tests with a tiny SQLite fixture DB.

Frontend tasks:

1. Create Vite app.
2. Add app shell with sidebar.
3. Add Overview page placeholder.
4. Fetch database status.
5. Show connected, disconnected, or error state.

Done when:

- pytest passes.
- Backend starts.
- Frontend starts.
- DB status appears in UI.

## Milestone 2 - Overview Report

Goal:

Show high-level historical poker data.

Backend tasks:

1. Find hero by HERO_NAME.
2. Count hands.
3. Count tournaments.
4. Count imported files.
5. Count HM3 error hands.
6. Find real date range excluding 1970 dates.
7. Count invalid 1970 hands.
8. Add endpoint:
   GET /api/reports/overview

Frontend tasks:

1. Show overview stat cards.
2. Show date range.
3. Show invalid date warning.
4. Show DB path basename only, not full sensitive path unless needed.
5. Show AI disabled state if AI is off.

Tests:

- Overview report with synthetic DB.
- 1970 dates are treated as invalid.
- Missing hero is reported clearly.

## Milestone 3 - Hand Review Queue

Goal:

Select useful historical hands for review.

Initial criteria:

- hands with all-in text
- large pots if pot can be parsed
- hands with hero name
- hands from error_hands
- recent hands with valid dates

Backend tasks:

1. Add hand selector service.
2. Add hand summary model.
3. Add endpoint:
   GET /api/hands/review-queue
4. Add endpoint:
   GET /api/hands/{hand_id}

Frontend tasks:

1. Add Hand Review page.
2. Show hand queue table.
3. Show selected hand text.
4. Add "Ask coach" button disabled if AI is off.

Tests:

- Selector returns deterministic ordering.
- Selector limits row count.
- Selector does not return empty hand text.

## Milestone 4 - AI Coach MVP

Goal:

Let AI analyze overview report and selected hands.

Backend tasks:

1. Add coach adapter interface.
2. Add mock adapter.
3. Add OpenAI-compatible adapter.
4. Add prompt templates.
5. Add endpoint:
   POST /api/coach/analyze-overview
6. Add endpoint:
   POST /api/coach/review-hand

Frontend tasks:

1. Add CoachPanel.
2. Add overview analysis action.
3. Add selected hand review action.
4. Show loading and error states.
5. Show AI disabled state.

Prompt output format:

1. Main leaks
2. Evidence
3. Hands to review
4. Study plan
5. Confidence and missing data

AI must cite report fields and hand IDs when possible.

## Milestone 5 - Leak Finder

Goal:

Add first leak finder metrics.

Start only with robust metrics.

Possible first metrics:

- hands by position if available
- tournament results if available
- import errors
- all-in frequency from text
- big lost pots if parsable
- valid vs invalid date coverage

Do not invent advanced stats unless they are actually supported by the database or parser.

## Testing

Run backend tests:

pytest

Run lint:

ruff check .

Run format:

ruff format .

If frontend exists, run:

cd frontend
npm run build

Add frontend tests later when UI behavior becomes complex.

## Test Fixtures

Use tiny synthetic SQLite databases in tests.

Fixture rules:

- no real personal data
- no real HM3 database
- no full hand history dumps
- small enough to inspect manually
- deterministic data

Suggested test fixture tables:

- players
- handhistories
- tournaments
- tournament_players
- imported_files
- error_hands

## Report Rules

Reports must be honest.

If data is missing, say it is missing.

If sample size is small, report low confidence.

If dates are invalid, show warnings.

If metric is unsupported, do not fake it.

## AI Adapter Rules

The AI adapter must be replaceable.

Required behavior:

- mock adapter for tests and no-key mode
- OpenAI-compatible adapter for real AI
- no hardcoded API keys
- no secrets in logs
- no full DB upload
- send only report JSON and selected hand text needed for the task

## Security Checklist

Before final response or commit:

- .env is not staged
- real .hmdb files are not staged
- generated reports are not staged unless approved
- no API keys in code
- no full personal hand history fixtures
- database opened read-only
- tests pass

## Git Workflow

Check status before work:

git status

Use small commits.

Good examples:

- init: add project scaffold
- db: add read only schema probe
- reports: add overview report
- hands: add review queue
- coach: add mock adapter
- ui: add app shell

Do not commit large generated files.

## Definition of Done

A task is done when:

- implementation is complete
- tests pass
- lint and format pass if configured
- docs are updated if behavior changed
- no secrets or DB files are committed
- git status is checked
- user gets a short Russian summary
