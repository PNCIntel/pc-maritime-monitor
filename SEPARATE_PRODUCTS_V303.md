# v3.0.3 — Separate Product Interfaces

- Removed all user-facing links from P&C Intelligence into the P&C Trade System.
- P&C Intelligence now keeps associated port, company, vessel and corridor context inside its own interface.
- The Trade System remains the commercial / asset / investment product.
- P&C Intelligence remains the security / operational / monitoring product.
- Both still read the same canonical Excel data today and can later read the same PostgreSQL/Supabase database.
- No data has been forked or duplicated.
