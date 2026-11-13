
# Agent Logging Format

## 1. Overview

The CV Tailoring Agent uses JSONL (JSON Lines) to record its execution.

Each line in a log file represents one independent JSON event.

Log files are stored in:

```text
logs/<run_id>.jsonl
```

Each agent run has a unique run ID.

## 2. Tool Call Event

A `tool_call` event is recorded after every tool execution.

| Field | Type | Description |
|---|---|---|
| event | string | Event type: `tool_call` |
| run_id | string | Unique execution identifier |
| step | integer | Agent step number |
| tool_name | string | Name of the executed tool |
| input | object | Arguments passed to the tool |
| output | object | Tool result or error |
| start_time | string | UTC timestamp in ISO 8601 format |
| duration_ms | number | Tool execution duration in milliseconds |
| tokens_in | integer | Input token count |
| tokens_out | integer | Output token count |

Token counts currently default to zero until model usage data is integrated.

## 3. Stop Event

A `stop` event is recorded when the agent finishes or a stop rule is triggered.

| Field | Type | Description |
|---|---|---|
| event | string | Event type: `stop` |
| run_id | string | Unique execution identifier |
| step | integer | Number of completed tool calls |
| stop_reason | string | Reason for stopping |
| timestamp | string | UTC timestamp in ISO 8601 format |

Possible stop reasons:

- `max_steps`
- `no_match`
- `repeated_call`
- `user_rejected`
- `done`

## 4. Example

```json
{"event":"tool_call","run_id":"test_run","step":1,"tool_name":"read_master_cv","input":{},"output":{"text":"Sample CV"},"start_time":"2026-11-13T12:00:00+00:00","duration_ms":12.5,"tokens_in":0,"tokens_out":0}
{"event":"stop","run_id":"test_run","step":1,"stop_reason":"done","timestamp":"2026-11-13T12:00:01+00:00"}
```

## 5. Security

- Sensitive dictionary values under recognized API-key, password, secret, authorization, and access-token keys are redacted.
- Never intentionally include credentials or secrets in tool inputs or outputs.
- Log data may contain CV and job-posting information. Treat log files as private project data.
- Tool results are recorded for debugging and evaluation.

## 6. Ownership

The agent logger is maintained by Student A.

The evaluation component should use these field names when processing agent logs.
