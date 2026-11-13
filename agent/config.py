
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
