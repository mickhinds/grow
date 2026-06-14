"""AI agents — Analyst and Voice, orchestrated by Python.

Two LLM roles, same model (Ministral 3B), different system prompts.
Python chains them: data_compiler → Analyst → Voice → stored result.

Why two calls instead of one?
  A single prompt that says "analyze this data AND write a friendly message"
  asks a 3B model to do two cognitive tasks at once. Small models are better
  at focused, single-purpose tasks. Splitting analysis from writing:
    - Analyst can be dry and structured (JSON output)
    - Voice can be warm and concise (natural text)
    - If the Analyst output is wrong, we can debug it separately
    - We can swap the Voice style without touching analysis logic

This is the same principle behind your RAG work: retrieval and generation
are separate steps because they require different skills.

Latency budget (Pi 5, Ministral 3B Q4_K_M, ~15-20 tok/s):
  Analyst: ~150 tokens → ~8s
  Voice:   ~80 tokens  → ~4s
  Total:   ~12s — fine for a background job, too slow for page load
"""

import json
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════════════
#
# These are the "brains" of each agent. On a 3B model, prompt engineering
# matters MORE than on GPT-4 or Claude — the model has less capacity to
# infer intent, so you need to be explicit about format and constraints.
#
# Tips for small model prompts:
#   1. Be extremely specific about output format
#   2. Give concrete examples (few-shot)
#   3. Keep system prompts short — they eat into context window
#   4. Use "Do NOT" for hard constraints (small models respect negation less)
#   5. JSON mode + schema description > hoping the model formats correctly

ANALYST_SYSTEM_PROMPT = """You are a health data analyst for a personal wellness app.

Your job: find the ONE most important insight from today's data. Not a summary — a pattern, correlation, or notable change that the user should know about.

INPUT: JSON with the user's health metrics (sleep, movement, fasting, calendar, weight, garden progress).

OUTPUT: JSON with exactly these fields:
{
  "insight": "One sentence describing the most notable pattern or observation",
  "priority": "high" or "medium" or "low",
  "mood": "empathy" or "encouragement" or "praise" or "neutral",
  "data_points": ["list of 1-3 specific numbers that support the insight"],
  "category": "sleep" or "movement" or "calendar" or "fasting" or "weight" or "pattern"
}

Rules:
- Focus on CHANGE and PATTERNS, not static numbers
- Compare to the user's own baseline, not general population
- If nothing notable happened, set priority to "low" and say so
- Never invent data — only reference numbers from the input
- Keep "insight" under 25 words"""

VOICE_SYSTEM_PROMPT = """You write brief messages for a health app called Grow. The user sees this message once in the morning.

Your tone: curious and warm. Like a friend who noticed something interesting, not a coach giving orders.

Rules:
- Maximum 2 sentences
- Never use the words: sisu, lagom, hygge, journey, hustle, grind, warrior
- Never use emojis
- Never give medical advice
- If the mood is "empathy", acknowledge difficulty without toxic positivity
- If the mood is "praise", be genuine and specific — not generic cheerleading
- If the mood is "encouragement", suggest one concrete small action
- Do NOT start with "Hey" or "Good morning" — the app already has a greeting

INPUT: A JSON insight from the analyst, plus the user's name.
OUTPUT: Just the message text, nothing else. No quotes, no labels."""

WEEKLY_ANALYST_PROMPT = """You are a health data analyst writing a weekly summary.

INPUT: JSON with 7 days of aggregated health metrics.

OUTPUT: JSON with exactly these fields:
{
  "headline": "One sentence capturing the week (under 15 words)",
  "wins": ["1-3 specific things that went well, with numbers"],
  "watch": ["0-2 things to watch next week, with numbers"],
  "pattern": "One cross-metric observation (e.g. how calendar affected sleep), or null",
  "overall_mood": "strong" or "steady" or "tough" or "mixed"
}

Rules:
- Reference specific numbers from the data
- Compare this week to previous week where available
- "wins" should be genuine — don't manufacture praise for mediocre data
- "watch" is curious, not alarming — "interesting that X" not "warning: X"
- If it was objectively a tough week, say so — honesty builds trust"""

WEEKLY_VOICE_PROMPT = """You write a brief weekly health summary for an app called Grow. This appears every Sunday.

Your tone: reflective, curious, warm. Like looking back at the week with a friend over coffee.

Rules:
- 3-5 sentences maximum
- Start with the headline insight, then key wins, then one thing to notice
- Never use: sisu, lagom, hygge, journey, hustle, grind
- Never use emojis
- Be honest — if it was a tough week, acknowledge it
- End with something forward-looking but not preachy

INPUT: A JSON weekly analysis plus the user's name.
OUTPUT: Just the summary text. No headings, no bullet points, no labels."""


# ═══════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

def generate_morning_insight(
    user_context: dict,
    ollama_client,
) -> Optional[dict]:
    """Run the full Analyst → Voice pipeline for a morning insight.

    Args:
        user_context: Output from data_compiler.compile_user_context()
        ollama_client: An OllamaClient instance

    Returns:
        dict with keys: {"message": str, "insight": dict, "source": "ai"}
        or None if anything fails (caller uses rule-based fallback)

    The flow:
        1. Serialize user_context to JSON
        2. Send to Analyst with ANALYST_SYSTEM_PROMPT → get structured insight
        3. Send insight + user name to Voice with VOICE_SYSTEM_PROMPT → get message
        4. Return both (insight for logging, message for display)
    """
    # Step 1: Prepare the data prompt
    # Keep it compact — remove None values and empty sections
    compact = _compact_context(user_context)
    data_prompt = json.dumps(compact, indent=None, default=str)

    # Guard: check total size. Ministral 3B has ~8K context.
    # System prompt ≈ 300 tokens, response ≈ 150 tokens → ~7500 tokens for input.
    # Rough estimate: 1 token ≈ 4 chars. So ~30K chars max.
    if len(data_prompt) > 25000:
        logger.warning(f"Data context too large ({len(data_prompt)} chars), trimming")
        # Drop correlations and garden detail to save space
        compact.pop("correlations", None)
        compact.pop("garden", None)
        data_prompt = json.dumps(compact, indent=None, default=str)

    # Step 2: Analyst
    logger.info("Running Analyst agent...")
    analysis = ollama_client.chat_json(
        system=ANALYST_SYSTEM_PROMPT,
        prompt=data_prompt,
        temperature=0.3,  # Low temp for analytical consistency
        max_tokens=300,
    )

    if not analysis:
        logger.warning("Analyst returned nothing — falling back to rules")
        return None

    # Validate required fields
    if "insight" not in analysis:
        logger.warning(f"Analyst output missing 'insight': {analysis}")
        return None

    # Step 3: Voice
    logger.info("Running Voice agent...")
    voice_prompt = json.dumps({
        "user_name": user_context.get("user", {}).get("name", ""),
        "analysis": analysis,
    })

    message = ollama_client.chat(
        system=VOICE_SYSTEM_PROMPT,
        prompt=voice_prompt,
        temperature=0.7,  # Slightly creative for natural language
        max_tokens=150,
    )

    if not message:
        # Voice failed but we have analysis — use the raw insight
        logger.warning("Voice agent failed — using analyst insight directly")
        message = analysis.get("insight", "")

    # Clean up common small-model artifacts
    message = _clean_output(message)

    return {
        "message": message,
        "insight": analysis,
        "source": "ai",
    }


def generate_weekly_report(
    weekly_context: dict,
    ollama_client,
) -> Optional[dict]:
    """Run the weekly Analyst → Voice pipeline for Sunday reports.

    Same structure as morning insight but with weekly prompts.
    """
    data_prompt = json.dumps(weekly_context, indent=None, default=str)

    # Step 1: Weekly Analyst
    logger.info("Running Weekly Analyst...")
    analysis = ollama_client.chat_json(
        system=WEEKLY_ANALYST_PROMPT,
        prompt=data_prompt,
        temperature=0.3,
        max_tokens=400,
    )

    if not analysis:
        return None

    # Step 2: Weekly Voice
    logger.info("Running Weekly Voice...")
    voice_prompt = json.dumps({
        "user_name": weekly_context.get("user_name", ""),
        "analysis": analysis,
    })

    message = ollama_client.chat(
        system=WEEKLY_VOICE_PROMPT,
        prompt=voice_prompt,
        temperature=0.7,
        max_tokens=250,
    )

    if not message:
        # Fallback: stitch together from analysis fields
        headline = analysis.get("headline", "Week in review.")
        wins = analysis.get("wins", [])
        message = headline
        if wins:
            message += " " + wins[0]

    message = _clean_output(message)

    return {
        "message": message,
        "analysis": analysis,
        "source": "ai",
    }


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _compact_context(ctx: dict) -> dict:
    """Remove None values and empty dicts/lists to save tokens."""
    if isinstance(ctx, dict):
        return {
            k: _compact_context(v)
            for k, v in ctx.items()
            if v is not None and v != {} and v != []
        }
    elif isinstance(ctx, list):
        return [_compact_context(i) for i in ctx if i is not None]
    return ctx


def _clean_output(text: str) -> str:
    """Remove common small-model artifacts from output.

    Small models sometimes:
    - Wrap output in quotes
    - Add labels like "Message:" or "Output:"
    - Include their thinking or caveats
    - Repeat the system prompt
    """
    text = text.strip()

    # Remove surrounding quotes
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1]

    # Remove common prefixes
    for prefix in ["Message:", "Output:", "Response:", "Here is", "Here's"]:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
            # Remove colon or dash after prefix
            if text.startswith(":") or text.startswith("-"):
                text = text[1:].strip()

    # Remove trailing disclaimers (small models love these)
    disclaimer_markers = [
        "Note:", "Disclaimer:", "Please note:",
        "Remember:", "Important:", "(This is not",
    ]
    for marker in disclaimer_markers:
        idx = text.find(marker)
        if idx > 20:  # Only if it's after real content
            text = text[:idx].strip()

    return text.strip()
