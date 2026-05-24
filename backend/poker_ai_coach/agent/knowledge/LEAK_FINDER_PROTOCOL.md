# Leak Finder Protocol

Leak Finder is AI-generated from safe local tools.

Required flow:

1. Load HM3 aggregate stats.
2. Load schema/stat mappings if needed.
3. Identify 1 to 3 likely leaks from stats.
4. Use hand search or tournament story only to select evidence hands.
5. Return confidence and missing data.

Output:

- Leak name
- Evidence from stats
- Hypothesis
- Hands to open
- Recommended drill
- Confidence

Do not make import errors or invalid dates the main leak unless no game data exists.
Do not invent solver claims.
