
"""
Central configuration for the CV Tailoring Agent.
All agent limits must be defined here.
"""

import os

# Maximum number of model decisions/tool calls per run.
MAX_STEPS = 12

# Stop if the skill matching score is below this threshold.
NO_MATCH_THRESHOLD = 0.25

# Maximum retries allowed for a failed tool.
MAX_RETRIES_PER_TOOL = 2

# Maximum number of times the agent can revise generated documents.
MAX_REVISIONS = 2

# Stop after this many identical consecutive tool calls.
MAX_SAME_CALL_REPEATS = 3

# Fixed candidate identifier used across all runs.
CANDIDATE_ID = "candidate_001"

# Directory for sandboxed output files.
SANDBOX_DIR = "sandbox"

# Seconds the checkpoint waits for interactive input before timing out.
CHECKPOINT_TIMEOUT_SECONDS = 120

# Token pricing — fill from the OpenAI pricing page for the model you use; do not guess.
PRICE_PER_MTOK_INPUT = 0.0
PRICE_PER_MTOK_OUTPUT = 0.0

# Maximum permitted API spending in USD.
# Zero means live paid requests are disabled until a budget is approved.
API_BUDGET_USD = float(os.environ.get("API_BUDGET_USD", "0"))

# Budget enforcement is implemented separately in the API adapters.
# Do not enable live paid requests until that protection is tested.
# Max tokens for model responses; 1024 truncated CVs and cover letters in JSON replies.
MODEL_MAX_TOKENS = 4096

# Default OpenAI model; unverified default — set CV_AGENT_MODEL to a model your key can use.
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

# Total tool-call steps across all turns before Session refuses new sends.
MAX_STEPS_PER_SESSION = 40

# Maximum messages kept in Session history before oldest are trimmed.
MAX_HISTORY_MESSAGES = 60

# Web mode: "fake" (offline default), "replay" (snapshot-backed), "live" (real sites/keys).
WEB_MODE = os.environ.get("WEB_MODE", "fake")

# Base URL for our own apply site. http is allowed only for loopback; use https otherwise.
OWN_SITE_BASE_URL = os.environ.get("OWN_SITE_BASE_URL", "http://127.0.0.1:5000")

# Maximum job results returned per find_jobs call.
MAX_JOBS_PER_SEARCH = 10

# Minimum seconds between consecutive requests to the same host (rate limiting).
SITE_THROTTLE_SECONDS = 3.0

# Maximum Browser Use agent steps per web task.
BROWSER_USE_STEP_LIMIT = 10

# Browser Use task timeout in seconds.
BROWSER_USE_TIMEOUT_SECONDS = 120

# Model used by Browser Use for autonomous web navigation.
BROWSER_USE_MODEL = os.environ.get("BROWSER_USE_MODEL", DEFAULT_OPENAI_MODEL)

# FIRECRAWL_API_KEY is env-only: read via os.environ.get("FIRECRAWL_API_KEY") where needed.
