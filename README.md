# P&C Research-First Analyst Loader v3.3 — API rate-limit resilience

This package is a hotfix on v3.2.

## What failed
The TWZ and additional article test reached the AI research stage but OpenAI returned HTTP 429 (Too Many Requests). The previous UI mixed these errors into the generic "Source errors" table, making them look like reader failures.

## Changes
- `pc_research_dossier.py`: bounded retry/backoff for OpenAI HTTP 429, 500, 502, 503 and 504 responses.
- Respects `Retry-After` when supplied by the API.
- Exponential fallback delay with small jitter when no `Retry-After` is supplied.
- Surfaces the OpenAI response body on permanent failure, so quota/rate-limit/auth problems are distinguishable.
- `pc-power-admin.py`: error rows now identify their stage (`fetch`, `file_parse`, `ai_research`, or `research_or_mapping`).
- The research-first dossier and database mapping logic are otherwise unchanged from v3.2.

## Test
1. Deploy the included Python files over v3.2 in staging.
2. Run ONE TWZ URL first.
3. If it succeeds, inspect/download `Research dossiers` before queuing.
4. Then test the second article.
5. If a 429 persists after retries, copy the full `ai_research` error text; it will now include the API response body and tell us whether this is a temporary request/token rate limit or account/quota issue.

No SQL migration is required.
