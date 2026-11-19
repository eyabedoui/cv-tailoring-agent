
"""
Central configuration for the CV Tailoring Agent.
All agent limits must be defined here.
"""

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

# Only URLs starting with this prefix are accepted by the mock tools.
ALLOWED_URL_PREFIX = "mock://"

# Seconds the checkpoint waits for interactive input before timing out.
CHECKPOINT_TIMEOUT_SECONDS = 120

# Token pricing — fill from the OpenAI pricing page for the model you use; do not guess.
PRICE_PER_MTOK_INPUT = 0.0
PRICE_PER_MTOK_OUTPUT = 0.0

# Max tokens for model responses; 1024 truncated CVs and cover letters in JSON replies.
MODEL_MAX_TOKENS = 4096

# Default OpenAI model; unverified default — set CV_AGENT_MODEL to a model your key can use.
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
