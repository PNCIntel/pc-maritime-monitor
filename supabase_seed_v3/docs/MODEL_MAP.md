# P&C Core Intelligence Model v3.0

```text
P&C CORE DATA
│
├── Entities
├── Assets & Infrastructure
├── Mobile Assets / Fleets
├── Ownership & Relationships
├── Geography & Corridors
├── Events
├── Security & Compliance
├── Financial & Investment Intelligence
├── Market Data
├── Intelligence Analysis
└── Sources & Observations
        │
        ├────────── P&C Trade System
        └────────── P&C Intelligence
```

## Important modeling rules
- Canonical vessels are anchored on IMO where available.
- Ownership/operator relationships are time-aware in the schema design.
- PGSA is a compliance regime, not collapsed into OFAC/EU/UK/UN sanctions.
- An event can link to many vessels, companies, assets and geographies.
- Weather, labour, security and regulatory events remain in the same event system.
- `record_status` and `data_quality` are explicit so provisional enrichment never masquerades as verified intelligence.
- Product visibility is a presentation/query concern, not a separate copy of the record.
