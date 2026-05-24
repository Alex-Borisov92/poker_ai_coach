# DB Safety Rules

The app is a local post-session coach.

Allowed:

- Read already played historical hands.
- Read HM3 SQLite in read-only mode.
- Send bounded JSON or one selected hand text to AI.
- Create sanitized schema snapshots without hand text.

Not allowed:

- No live poker help.
- No poker client integration.
- No raw SQL tool.
- No DB writes to HM3.
- No full `.hmdb` upload.
- No API keys or full paths in responses.

SQLite must be opened with URI read-only mode.
