# Error taxonomy

One row per error class. Every class needs at least one test. The "Test ids" column is filled in during Week 2 (D7).

| Class | What the agent does | Planned test and scenario | Test ids | Owner |
|---|---|---|---|---|
| Tool down | Retries a transient error up to 2 times, then stops with a clear message | FAULT_MODE=down (B6), A5 test | TBD | B6, A5 |
| Bad arguments | Tool returns INVALID_ARGUMENTS, the model corrects the call, no retry loop | Schema rejection test (B2), C5 scenario | TBD | B2, C5 |
| Empty result | Treats an empty or missing posting as a stop, not a guess | Empty posting test (B7), C5 scenario | TBD | B7, C5 |
| Wrong tool | Unknown tool or wrong order returns an error, submit is refused before CV and cover letter exist | Loop test, C5 scenario | TBD | A5, C5 |
| Loop | Stops on the same call three times (repeated_call) or at 12 steps | A6 tests | TBD | A6 |
| Timeout | Tool timeout is retried, checkpoint timeout counts as rejection | FAULT_MODE=timeout (B6), checkpoint timeout test (A6) | TBD | B6, A6 |
| User changes mind | Reject stops with no submit, change request allows at most 2 revisions | A7 tests, C5 scenarios | TBD | A7, C5 |
