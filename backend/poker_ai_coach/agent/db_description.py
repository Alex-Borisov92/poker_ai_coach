DB_DESCRIPTION = """
HM3 database is local SQLite opened read-only.
Useful tables:
- handhistories: handhistory_id, gamenumber, handhistory, handtimestamp, tournament_number
- tournaments: tournament_number, timestamps, entrants, buyin/rake/bounty/prize fields
- tournament_players: player_id, tournament_id, finish_position, winnings fields
- players: player_id, playername
- error_hands: import error rows, not always linkable to handhistory_id

Rules:
- 1970-01-01 dates are invalid or unknown.
- Do not infer unsupported HUD stats.
- VPIP, PFR, 3bet, cbet, ROI, ICM, and bounty conclusions require explicit tool evidence.
- Prefer hand IDs, tournament clusters, stack depth, actions, large pots, and all-in spots.
""".strip()


UNSUPPORTED_STATS = ["VPIP", "PFR", "3bet", "cbet", "HUD stats", "solver EV"]
