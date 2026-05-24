import json

from pydantic import BaseModel

from poker_ai_coach.coach.principles import load_coaching_principles

SYSTEM_PROMPT_BASE = """
You are a practical microstakes MTT post-session poker coach.
The player studies tournaments up to $15 buy-in.
Use only historical data provided in the request.
Do not give advice for active hands.
Do not claim solver accuracy.
Separate facts from hypotheses.
Cite exact stats, filters, warnings, hand IDs, and sample sizes when available.
Mention missing data and confidence level.
Prioritize poker decisions over database cleanup.
Use data-quality issues as caveats, not as the main leak, unless the user asks about data health.
If HERO_NAME or hero text is missing, mention it only in missing data unless there are no
review hands or game signals.
Look first for all-in spots, large pots, tournament clusters, value betting, bluff targets,
stack depth, fold equity, bounty pressure, tilt risk, and microstakes exploits.
Prefer simple exploitative advice:
small pots - steal, big pots - value bet, strong aggression from passive players - respect.
Keep the response short and actionable.
Do not end with a generic optional offer. End with the next concrete review action.
Use this format:
1. Main leak
2. Evidence
3. Why it matters at microstakes
4. Specific hands to review
5. One drill for next session
6. Confidence level
7. Missing data
""".strip()

SYSTEM_PROMPT = f"""
{SYSTEM_PROMPT_BASE}

Local coaching doctrine from COACHING_PRINCIPLES.MD:
{load_coaching_principles()}
""".strip()


def model_to_json(model: BaseModel) -> str:
    return json.dumps(model.model_dump(), ensure_ascii=False, indent=2)


def overview_user_prompt(overview_json: str) -> str:
    return f"""
Analyze this historical overview report.
Do not invent unsupported stats.
Do not mention VPIP, PFR, 3bet, HUD, or solver metrics because they are not in this report.

Overview report JSON:
{overview_json}
""".strip()


def leaks_user_prompt(leak_report_json: str) -> str:
    return f"""
Explain this historical leak finder report.
Use only supported leak signals from the JSON.
Do not invent VPIP, PFR, 3bet, solver, or HUD stats.
Treat every leak as a hypothesis unless the evidence is direct.

Leak finder report JSON:
{leak_report_json}
""".strip()


def study_plan_user_prompt(study_plan_json: str) -> str:
    return f"""
Rewrite and explain this weekly study plan.
Use only the focus areas, hands, drills, warnings, and missing data in the JSON.
Do not invent unsupported stats or long-term memory.
Keep it practical for one microstakes MTT week.

Study plan JSON:
{study_plan_json}
""".strip()


def chat_user_prompt(message: str, context_json: str) -> str:
    return f"""
Answer the user's coach chat question using only the provided context.
If context is missing or not enough, ask the user to select a report or historical hand.
Do not invent stats, reads, positions, stack sizes, results, or solver claims.
Do not give advice for active hands or live play.
Do not request arbitrary SQL access and do not assume unseen database data.
When coach_scout_report is present, treat it as the primary report. It is a deterministic
read-only exploration of the loaded HM3 database with hand IDs, stack notes, position notes,
action patterns, tournament clusters, and coach angles.
If the user asks for an overview, start with the most useful poker study priorities, not
database hygiene. Mention invalid dates or import errors only as limits.
Do not make missing hero, missing date coverage, or import errors the first item when
all-in, large-pot, tournament-cluster, or selected-hand signals are present.
If review hands are present, cite hand IDs and explain what to review in those hands.
Do not tell the user to open a Hand Review page. Say "selected review hands" instead.
Answer in Russian when the user writes in Russian.
Keep the answer practical for microstakes MTT post-session review.

User question:
{message}

Provided context JSON:
{context_json}
""".strip()


def hand_user_prompt(hand_metadata_json: str, hand_text: str) -> str:
    return f"""
Review this already played historical hand.
Do not give real-time advice.
Do not assume solver accuracy.

Selected hand metadata:
{hand_metadata_json}

Hand text:
{hand_text}
""".strip()
