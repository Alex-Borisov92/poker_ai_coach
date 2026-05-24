# AGENTS.md

## Project Name

poker-ai-coach

## Main Goal

Build a local web app that works as a post-session AI poker coach for a microstakes MTT player.

The app reads a local Holdem Manager 3 SQLite database in read-only mode, generates poker reports, shows them in a local web UI, and lets the user ask an AI coach to analyze stats and selected historical hands.

This is not a real-time poker assistant, not a HUD, not a solver, and not a gameplay tool.

## Language Rules

- Talk to the user in Russian.
- Use simple English in code, comments, docstrings, tests, docs, commit messages, and UI technical labels.
- Keep explanations short and practical.
- Do not use long dash characters. Use normal hyphen only.

## User Context

Hero nickname: surok_valera

Expected local database: HM3 SQLite .hmdb file.

Example env values:

HM3_DB_PATH=C:\Users\aleks\Desktop\pokerdom.hmdb
HERO_NAME=surok_valera

The user wants the app to work like a practical microstakes MTT coach after sessions.

## Product Goal

For a selected period, the app should:

1. Open the HM3 SQLite database in read-only mode.
2. Detect database health and schema.
3. Find hero stats and historical hands.
4. Generate safe reports.
5. Select hands for review.
6. Show reports and hand text in a local web UI.
7. Let AI analyze reports and selected hands.
8. Create a short study plan.

## Safety Rules

Allowed:

- Read already played historical hands.
- Read local HM3 database in read-only mode.
- Analyze results after a session.
- Generate reports, hand review queues, and study plans.
- Use AI to explain historical stats and historical hands.

Not allowed:

- Do not interact with active poker tables.
- Do not build real-time decision support.
- Do not connect to poker clients.
- Do not scrape live tables.
- Do not make betting decisions during play.
- Do not modify the HM3 database.
- Do not store secrets, cookies, tokens, or private DB files in git.
- Do not upload full personal hand databases to third-party services.
- Do not commit real personal hand history data.

## AI Coach Rules

The AI coach should:

- Act as a practical microstakes MTT coach.
- Focus on actionable leaks.
- Prefer simple exploitative advice over abstract theory.
- Separate facts from hypotheses.
- Cite exact stats, filters, and hand IDs when possible.
- Mention sample size and missing data.
- Give short study plans.
- Avoid pretending unsupported stats exist.

The AI coach must not:

- Claim solver accuracy.
- Give advice for active hands.
- Invent stats not present in the report.
- Ignore sample size.
- Pretend a hypothesis is a proven leak.

## Technical Stack

Preferred stack:

- Backend: Python 3.11+
- API: FastAPI
- DB access: sqlite3 or SQLAlchemy Core
- Data models: Pydantic
- Frontend: React + TypeScript + Vite
- Tests: pytest for backend
- Formatting and linting: ruff

## Database Rules

Open SQLite in read-only mode.

Use URI mode:

file:<path>?mode=ro

Never execute:

- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- CREATE
- VACUUM
- ATTACH

Reports should use safe repository functions, not arbitrary SQL from the UI.

If a raw SQL tool is ever added, it must be disabled by default, SELECT-only, and limited.

## Known HM3 Tables

Known useful tables from the current sample:

- handhistories
- tournaments
- tournament_players
- players
- player_hands
- pokertables
- gametypes
- imported_files
- import_summaries
- error_hands

Important known fields:

handhistories:

- handhistory_id
- gamenumber
- pokersite_id
- handhistory
- filename
- handtimestamp
- gametype_id
- tournament_number

tournaments:

- tournament_id
- site_id
- tournament_number
- first_hand_timestamp
- last_hand_timestamp
- gametype_id
- number_of_entrants
- buyin_in_cents
- rake_in_cents
- bounty_in_cents
- prize_pool_in_cents

players:

- player_id
- playername
- pokersite_id
- tourneyhands

tournament_players:

- player_id
- tournament_id
- finish_position
- winnings_in_cents

## Date Caveat

Some imported hands may have:

1970-01-01

Treat 1970 dates as invalid or unknown.

Reports must show warnings when date coverage is incomplete.

Do not silently use 1970 as a real session date.

## Expected Project Structure

poker-ai-coach/
  AGENTS.md
  DEVELOPMENT.md
  README.md
  .env.example
  .gitignore
  pyproject.toml
  backend/
    poker_ai_coach/
      __init__.py
      config.py
      main.py
      db/
        __init__.py
        hm3_connection.py
        schema_probe.py
      repositories/
        __init__.py
        hm3_repository.py
      reports/
        __init__.py
        overview.py
        positions.py
        hand_review_queue.py
      coach/
        __init__.py
        prompts.py
        service.py
        openai_adapter.py
        mock_adapter.py
      models/
        __init__.py
        reports.py
        hands.py
        coach.py
      api/
        __init__.py
        health.py
        database.py
        reports.py
        hands.py
        coach.py
  frontend/
    package.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
      api/
        client.ts
      layout/
        AppShell.tsx
      pages/
        OverviewPage.tsx
        LeakFinderPage.tsx
        HandReviewPage.tsx
        TournamentsPage.tsx
        StudyPlanPage.tsx
        CoachChatPage.tsx
        SettingsPage.tsx
      components/
        StatCard.tsx
        DataTable.tsx
        HandTextViewer.tsx
        CoachPanel.tsx
        DateRangePicker.tsx
        FilterBar.tsx
  tests/
    fixtures/
    test_schema_probe.py
    test_reports_overview.py
    test_hand_review_queue.py

## UI Rules

Build a local app UI, not a landing page.

Main layout:

- Left sidebar navigation.
- Center report and hand review area.
- Right AI coach panel when useful.

Sidebar pages:

- Overview
- Leak Finder
- Hand Review
- Tournaments
- Study Plan
- Coach Chat
- Settings

Design style:

- Quiet poker analysis dashboard.
- Dense but readable.
- No marketing hero page.
- No decorative gradient orbs.
- No card-inside-card layouts.
- Use tables, filters, charts, and compact panels.
- Use cards only for stat cards and repeated items.
- Make text fit on desktop and mobile.

## MVP Order

Milestone 1:

- Project scaffold.
- Backend health endpoint.
- Read env config.
- Open HM3 SQLite read-only.
- Probe schema and table counts.
- Tests for read-only connection and schema probe.
- Minimal frontend shell with sidebar and DB status placeholder.

Milestone 2:

- Overview report.
- Find hero by HERO_NAME.
- Count hands, tournaments, imported files, error hands.
- Show real date range, excluding 1970 dates.
- Show invalid date warnings.
- Frontend Overview page.

Milestone 3:

- Hand review queue.
- Select interesting historical hands.
- Show hand list and hand text viewer.
- Add tests with tiny fixture DB.

Milestone 4:

- AI coach MVP.
- Adapter interface.
- Mock adapter.
- OpenAI-compatible adapter.
- Report analysis prompt.
- Selected hand review prompt.
- Coach panel in UI.

Milestone 5:

- Leak Finder.
- Add robust metrics only.
- Show unavailable metrics honestly.
- Add confidence levels.

## Development Workflow

Before coding:

1. Inspect existing files.
2. Read AGENTS.md.
3. Read DEVELOPMENT.md.
4. Check git status.
5. Understand the current task.
6. Propose a short plan.
7. Then modify files.

When coding:

1. Work in small iterations.
2. Add or update tests when practical.
3. Implement the minimum useful code.
4. Run tests.
5. Run lint and format checks if configured.
6. Summarize changed files and verification.

Do not generate a large untested project in one pass.

## Git Rules

Do not commit:

- .env
- API keys
- tokens
- cookies
- real HM3 databases
- real hand history dumps
- generated personal reports
- screenshots with sensitive data

Safe files:

- source code
- tests
- tiny synthetic fixtures
- docs
- .env.example

Good commit messages:

- init: add project scaffold
- db: add read only hm3 connection
- reports: add overview report
- hands: add review queue selector
- coach: add mock ai adapter
- ui: add overview page

## Definition of Done

A task is done only when:

- Code is implemented.
- Tests pass.
- Formatting and lint pass if configured.
- No secrets or DB files are committed.
- README or docs are updated if behavior changed.
- Git status is checked.
- The user receives a concise Russian summary.