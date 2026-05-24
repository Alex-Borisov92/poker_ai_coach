# HM3 Schema Guide

Use this guide when exploring a local Holdem Manager 3 SQLite database.

Core tables:

- `players`: player identity, hero lookup, site ids, hand counts.
- `compiledplayerresults`: HM3 aggregate counters by player, month, game type, table size, and blind group.
- `handhistories`: historical hand text and metadata. Use only selected hand IDs.
- `tournaments`: tournament metadata, buy-in, rake, bounty, entrants, timestamps.
- `tournament_players`: hero finish position, winnings, bounty count, rebuys, addons.
- `gametypes`: blinds, antes, table size, tournament flag.
- `imported_files`, `import_summaries`, `import_details`: import coverage and import quality.
- `error_hands`: failed import rows. Treat as data-quality caveat.

Coaching priority:

1. Start from aggregate stats in `compiledplayerresults`.
2. Use hand text only to verify a stat hypothesis or select review hands.
3. Use tournament tables for tournament story, finish coverage, buy-ins, and bounty context.
4. Treat `1970-01-01` as unknown date.

Do not request raw SQL or full database upload.
