
"""
Central configuration for the CV Tailoring Agent.

All agent limits and provider configurations are defined here.
API credentials must be stored in .env, never in this file.
"""

import os


# ============================================================
# Agent limits
# ============================================================

MAX_STEPS = 12

NO_MATCH_THRESHOLD = 0.25

MAX_RETRIES_PER_TOOL = 2

MAX_REVISIONS = 2

MAX_SAME_CALL_REPEATS = 3

CANDIDATE_ID = "candidate_001"

SANDBOX_DIR = "sandbox"

CHECKPOINT_TIMEOUT_SECONDS = 120

MODEL_MAX_TOKENS = 4096

MAX_STEPS_PER_SESSION = 40

MAX_HISTORY_MESSAGES = 60


# ============================================================
# OpenAI configuration
# ============================================================

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

# Keep OpenAI pricing disabled until official prices are set.
PRICE_PER_MTOK_INPUT = 0.0
PRICE_PER_MTOK_OUTPUT = 0.0

# Zero prevents paid requests until a budget is approved.
API_BUDGET_USD = float(
    os.environ.get("API_BUDGET_USD", "0")
)


# ============================================================
# Groq configuration
# ============================================================

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

GROQ_MODEL = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

# Groq pricing must be configured separately from OpenAI.
# Zero means pricing has not yet been configured.
GROQ_PRICE_PER_MTOK_INPUT = float(
    os.environ.get("GROQ_PRICE_PER_MTOK_INPUT", "0")
)

GROQ_PRICE_PER_MTOK_OUTPUT = float(
    os.environ.get("GROQ_PRICE_PER_MTOK_OUTPUT", "0")
)

# Groq spending cap.
# Keep at zero until a budget is approved.
GROQ_API_BUDGET_USD = float(
    os.environ.get("GROQ_API_BUDGET_USD", "0")
)


# ============================================================
# Web configuration
# ============================================================

# Modes: fake, replay, live.
WEB_MODE = os.environ.get("WEB_MODE", "fake")

OWN_SITE_BASE_URL = os.environ.get(
    "OWN_SITE_BASE_URL",
    "http://127.0.0.1:5000",
)

MAX_JOBS_PER_SEARCH = 10

SITE_THROTTLE_SECONDS = 3.0


# ============================================================
# Browser Use configuration
# ============================================================

BROWSER_USE_STEP_LIMIT = 10

BROWSER_USE_TIMEOUT_SECONDS = 120

BROWSER_USE_MODEL = os.environ.get(
    "BROWSER_USE_MODEL",
    DEFAULT_OPENAI_MODEL,
)


# ============================================================
# API credentials
# ============================================================

# Never hardcode API keys here.
#
# OPENAI_API_KEY: stored in .env
# GROQ_API_KEY: stored in .env
# FIRECRAWL_API_KEY: stored in .env
#
# The relevant API adapters read credentials from os.environ.
