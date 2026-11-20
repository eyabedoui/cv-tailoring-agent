
# CV Tailoring Agent — API Cost Model

**Project:** CS496 Project 3 — CV Tailoring Agent  
**Responsible:** Person A  
**Status:** PENDING TEAM AND INSTRUCTOR APPROVAL  
**Last updated:** 2026-11-20

## 1. Objective

This document defines the proposed spending limits for the
external services used by the CV Tailoring Agent.

The goal is to prevent unexpected API expenses during
development, testing, and evaluation.

No paid API usage is authorized until the budget is approved.

## 2. Services

The project uses three external services:

| Service | Purpose | Budget status |
|---|---|---|
| OpenAI | Agent reasoning and CV tailoring | Pending approval |
| Firecrawl | Reading and extracting job postings | Pending approval |
| Browser Use | Browser automation for the fake job portal | Pending approval |

## 3. Proposed Budget

The following limits are suggestions for team discussion.
They are NOT approved spending authorizations.

| Service | Proposed maximum | Status |
|---|---|---|
| OpenAI API | $3.00 USD | PENDING APPROVAL |
| Firecrawl | Free-tier credits only | PENDING APPROVAL |
| Browser Use | $2.00 USD equivalent | PENDING APPROVAL |
| Total paid spending | $5.00 USD | PENDING APPROVAL |

Important:

- These values are proposals, not confirmed limits.
- Browser Use costs depend on the chosen model and provider.
- Free-tier availability and included credits must be
  checked against the provider's current account settings.
- If Browser Use uses the same OpenAI billing account,
  its token costs must count toward the shared OpenAI cap.
  The proposed amounts must not be treated as independent
  allowances unless separate billing limits are configured.
- The team must agree on the final amounts before activation.

## 4. Current Safe Configuration

Until approval:

API_BUDGET_USD=0

In agent/config.py:

PRICE_PER_MTOK_INPUT = 0.0
PRICE_PER_MTOK_OUTPUT = 0.0

These settings prevent paid OpenAI requests through the
budget-protected agent execution path.

They do not control unrelated scripts or direct provider
API calls.

No real paid requests should be made during this phase.

## 5. Cost Calculation

OpenAI usage is calculated from input and output tokens.

Estimated cost in USD:

(input_tokens * input_price_per_million
 + output_tokens * output_price_per_million)
 / 1,000,000

Example using hypothetical prices:

Input tokens: 1,000
Output tokens: 500
Input price: $1.00 per million tokens
Output price: $2.00 per million tokens

Estimated cost:

(1000 * 1.00 + 500 * 2.00) / 1,000,000

= $0.002

These example prices are NOT actual provider prices.

Before live testing, obtain the current prices from the
official provider pricing pages.

## 6. Implemented Budget Controls

The agent includes the following components:

- agent/token_counter.py:
  Estimates input token usage.

- agent/costs.py:
  Calculates estimated and actual token costs.

- agent/budget.py:
  Reserves budget, records spending, and tracks
  the remaining amount.

- agent/model.py:
  Checks available budget before sending OpenAI
  requests and settles successful requests using
  reported token usage.

- agent/logger.py:
  Records usage information for evaluation.

Current verification:

- 49 OpenAI model tests passed.
- Zero-budget protection tested.
- Missing-pricing protection tested.
- Actual-cost settlement tested.
- Missing-usage reservation retention tested.

Limitations:

- Token estimates are not guaranteed upper bounds.
- Actual charges can exceed estimated reservations.
- Reservations may remain after failed requests.
- Budget state is not persistent across process restarts.
- Other API clients may bypass this budget tracker.
- Provider-side billing limits are not configured yet.

Therefore, these controls do not currently constitute
a guaranteed hard spending cap.

## 7. Provider Dashboard Limits

### OpenAI

Status: NOT CONFIGURED / NOT VERIFIED

Required actions:

1. Obtain the approved spending limit.
2. Identify the correct instructor-provided API project.
3. Configure the available project budget and usage alerts.
4. Confirm whether the provider offers an enforceable
   hard spending limit for this account.
5. Do not treat alerts or soft budgets as hard limits.
6. Record the configuration and verification date.

### Firecrawl

Status: NOT CONFIGURED / NOT VERIFIED

Required actions:

1. Confirm available free-tier credits.
2. Agree on the maximum credit consumption.
3. Configure provider-side credit restrictions where available.
4. Disable or avoid automatic paid upgrades.
5. Verify the account cannot exceed the approved
   spending amount without authorization.
6. Record the configuration and verification date.

### Browser Use

Status: NOT CONFIGURED / NOT VERIFIED

Required actions:

1. Select the Browser Use model and execution mode.
2. Verify the billing provider.
3. Agree on a token or cost limit.
4. Set BROWSER_USE_STEP_LIMIT and timeout settings.
5. Include model token charges in the correct
   provider's shared spending budget.
6. Configure any available provider-side limits.
7. Record the configuration and verification date.

## 8. Approval Record

| Decision | Value | Status |
|---|---|---|
| OpenAI spending cap | Not agreed | PENDING |
| Firecrawl credit cap | Not agreed | PENDING |
| Browser Use token cap | Not agreed | PENDING |
| Agent model | Not confirmed | PENDING |
| Browser Use model | Not confirmed | PENDING |
| Instructor authorization | Not confirmed | PENDING |
| Provider dashboard limits | Not configured | PENDING |

Approved by: ____________________

Approval date: ____________________

Final approved total: ____________________

## 9. Activation Checklist

Before enabling live paid requests:

- [ ] Team agrees on spending limits.
- [ ] Instructor confirms the permitted API provider
      and models.
- [ ] Official model pricing is verified.
- [ ] Provider dashboard limits are configured.
- [ ] Hard-limit availability and enforcement are verified.
- [ ] Firecrawl credit restrictions are verified.
- [ ] Browser Use spending is accounted for.
- [ ] API keys are stored locally in .env.
- [ ] .env is excluded from Git.
- [ ] Budget controls are tested with mock responses.
- [ ] Paid testing is explicitly authorized.

## 10. Final Status

A-0c — Spending Cap

Current status: IN PROGRESS

Completed:
- Proposed budget documented.
- Local OpenAI cost tracking implemented.
- Basic budget and settlement tests passed.

Remaining:
- Team approval.
- Instructor confirmation where required.
- Provider dashboard configuration.
- Verification of enforceable spending restrictions.

No paid API usage is authorized at this stage.
