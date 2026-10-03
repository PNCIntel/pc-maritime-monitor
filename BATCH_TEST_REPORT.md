# Batch loader validation — v3.6.0

54 offline tests and compile checks pass.

| Scenario | Result |
| --- | --- |
| 20 source graphs share one company | One canonical proposal; 20 distinct source contexts |
| Article claims and incident contexts | Each source retains its own claims/event |
| 20 URL labels plus two newsletter inputs | 22 contexts, 24 event proposals, one existing company |
| Repeat publication | No additional canonical events or company rows |
| One rejected publication | 19 other event proposals publish; rejected stage isolated |
| Conflicting or duplicate existing event identity | Events held; independent company remains queueable |
| One vessel and incident reported by two sources | One vessel, event and involvement link; both source URLs retained |
| Older company research holds | Exact existing identity eligible; no CREATE, type or country conflict bypass |
| Identity-only publisher RPC payload | Existing canonical values only; uncertain claims not promoted |
| Publisher failure during identity matching | Original staging restored, research journal unchanged |
| Interrupted payload preparation | Saved original proposal recovered from durable job checkpoint |
| Word newsletter tables | Extracted alongside paragraph text |
| Printed PDF text and embedded URL | Extracted without creating a document-table record |
| Structured invalid IMO or military-unit infrastructure | Held by publication validation |
| Existing company/document regression coverage | Includes repeated uploads, issuer evidence, company facets and source graph validation |

The Supabase RPCs and AI graphs in integration tests are doubles. Generated graph
facts are labelled fixture-only and are not statements about the linked articles.
The tests make no production writes and are not proof of deployed RPC behavior.

The previous supplied database export was also replanned. The four legacy held
company stages resolve to their existing canonical IDs as identity-only matches.
Their saved research holds remain retained. This was a read-only, offline replay
of exported records; the latest deployed database state may differ.

## Actual network/API attempt

The application's URL reader was executed against the 20 real publisher URLs
listed in `fixtures/BATCH_20_URLS.txt`. All attempts failed at DNS resolution with
`Temporary failure in name resolution`. Results are in `URL_READER_ATTEMPT.json`.
No runtime OpenAI API key is configured here, so fresh AI extraction was not run.
No live Supabase publication was attempted. Four article pages were independently
opened through web retrieval, which does not test the app's network environment.

## Remaining live checks

Run URL retrieval and AI extraction in the deployed app, with its configured key.
Confirm source-root precision, article dates, source attribution, SQL constraints,
publication audit entries, canonical entity preservation, involvement links,
company/document enrichment and retry behavior. Examine the downloaded complete
population JSON. Pending acquisitions and unresolved incident claims must stay
qualified; legacy factual/source errors are not independently repaired by these tests.
