# Manual QA Test Cases

## Scope

Use these cases for local post-session QA. The goal is to check whether the MVP helps a
microstakes MTT player find practical study work from historical data.

Do not test live poker tables, poker clients, or real-time decisions.

## Preconditions

- Backend is running.
- Frontend is running.
- `.env` points to a local HM3 `.hmdb` file.
- `HERO_NAME` is set.
- AI can be enabled or disabled, but API keys must not be shown in the UI or logs.
- Database status shows only the database basename, not the full local path.

## Leak Finder

### LF-01 Loads Supported Signals

Steps:

1. Open the app.
2. Click `Leak Finder`.
3. Wait until loading finishes.

Expected:

- Page shows total hands.
- Page shows a compact list of supported leak signals.
- Each item has leak name, evidence, confidence, action, and related hands when available.
- Unsupported stats such as VPIP, PFR, 3bet, and solver output are not shown.

### LF-02 Data Quality Is Honest

Steps:

1. Open `Leak Finder`.
2. Inspect invalid date and import error signals.

Expected:

- `1970-01-01` hands are treated as unknown.
- Date warnings explain that date-filtered conclusions may be incomplete.
- Import errors are shown as data quality or review priority, not as a proven poker leak.

### LF-03 Gameplay Signals Are Prioritized

Steps:

1. Open `Leak Finder`.
2. Inspect all-in, large-pot, and selected tournament cluster items.

Expected:

- All-in and large-pot items include related hand IDs.
- Evidence uses the selected review queue size or total hand count clearly.
- Recommended actions mention stack depth, fold equity, bounty context, value target,
  bluff target, SPR pressure, or tilt risk.
- The report does not claim that a high all-in count is automatically bad.

### LF-04 Tournament Result Coverage

Steps:

1. Open `Leak Finder`.
2. Inspect missing data and tournament result items.

Expected:

- If buy-in, winnings, or finish data are missing, the page says so.
- ROI or result pressure appears only when cost and return values are usable.
- Result pressure is treated as variance-aware and low or medium confidence.

### LF-05 AI Explains Leaks

Steps:

1. Open `Leak Finder`.
2. Click `Explain leaks`.
3. Wait for the coach response.

Expected:

- The response cites evidence from the leak report.
- The response separates facts from hypotheses.
- The response does not invent VPIP, PFR, 3bet, HUD, solver, or unseen stats.
- The response gives one practical next drill.

## Study Plan

### SP-01 Loads Weekly Plan

Steps:

1. Click `Study Plan`.
2. Wait until loading finishes.

Expected:

- Page shows focus areas, hands to review, drills, weekly checklist, confidence, and warnings.
- Focus areas are based on leak signals and review hands.
- Hands table includes hand ID, tournament, date or unknown, reason, and source.

### SP-02 Gameplay Focus Comes First

Steps:

1. Open `Study Plan`.
2. Read the first three focus areas.

Expected:

- Gameplay review topics such as large pots, all-ins, tournament cluster, or result pressure
  are preferred over pure database cleanup when available.
- Data quality remains visible as warnings or missing data.
- The plan does not recommend changing strategy from results alone.

### SP-03 Drills Are Actionable

Steps:

1. Open `Study Plan`.
2. Read `Drills` and `Weekly checklist`.

Expected:

- Drills can be done in one week.
- Drills mention practical review work, such as stack depth, fold equity, bounty context,
  value target, bluff target, SPR pressure, or tournament story review.
- Checklist is short and usable before or after a session.

### SP-04 AI Explains Plan

Steps:

1. Open `Study Plan`.
2. Click `Explain plan`.
3. Wait for the coach response.

Expected:

- AI uses only the current plan context.
- AI cites focus areas, hand IDs, warnings, and missing data.
- AI keeps the plan practical and short.
- AI does not create new unsupported stats.

## AI Coach Chat

### CC-01 Coach Opens As Main Screen

Steps:

1. Open the app.
2. Confirm `Coach Chat` is the first active screen.

Expected:

- Sidebar shows `Coach Chat`, `Overview`, `Leak Finder`, `Study Plan`, and `Settings`.
- `Hand Review` and `Tournaments` are not primary navigation items.
- The right panel explains that the coach automatically uses Overview, Leak Finder,
  Study Plan, and selected review hands.

### CC-02 Disabled States Are Clear

Steps:

1. Open `Coach Chat`.
2. Try to send an empty question.

Expected:

- Send button is disabled.
- The right panel asks for a focused post-session question or AI setup.
- The UI does not say AI is disabled when AI is configured but the question is empty.

### CC-03 Grounded Question

Steps:

1. Ask: `дай оверью как тренер, больше по игре и рукам, не по качеству базы`.
2. Click `Ask coach`.
3. Wait for the answer.

Expected:

- The answer uses the automatic coach context only.
- The answer starts with poker study priorities, not database hygiene.
- The answer cites hand IDs or tournament clusters when available.
- The answer does not request arbitrary SQL.
- The answer does not give live hand advice.
- The answer does not invent VPIP, PFR, 3bet, solver output, or unseen results.
- Technical warnings such as `error_hands.handhistory_id is missing` are not shown
  in the coach answer.

### CC-04 Chat History

Steps:

1. Ask a question and wait for the answer.
2. Reload the page.
3. Click `Clear history`.

Expected:

- Previous messages remain after reload.
- `Clear history` removes local messages.
- History is local browser storage only.

## Regression Smoke

Run these after each fix:

- `pytest`
- `ruff check .`
- `ruff format --check .`
- `cd frontend && npm run check`
- `cd frontend && npm run build`

Runtime smoke:

- `GET /api/health`
- `GET /api/database/status`
- `GET /api/reports/overview`
- `GET /api/reports/leak-finder`
- `GET /api/study-plan`
- `POST /api/coach/analyze-leaks`
- `POST /api/coach/study-plan`
- `POST /api/coach/chat`
