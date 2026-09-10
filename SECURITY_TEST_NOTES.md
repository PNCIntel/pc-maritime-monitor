# P&C v2.9 — Security / PGSA Test Layer

This package keeps the existing v2.9 canonical model and adds a sample security/compliance enrichment layer.

## What was added
- Canonical sample vessels: GasLog Shanghai and Al Rekayyat.
- Existing canonical vessels Mraweh and Tarif linked to PGSA restrictions.
- Time-ready vessel/company relationships for ownership/operator testing.
- PGSA modeled as a dedicated maritime compliance regime, separate from OFAC/EU/UK/UN sanctions.
- PGSA direct designations and secondary STS exposure examples.
- Official MARSEC source feeds for Japan Coast Guard, Korea Coast Guard, Indian Coast Guard and DG Shipping India.
- Sample official-source maritime events for Japan, South Korea and India.
- Security monitoring records and a Security Product View showing how the same canonical records serve P&C Intelligence and the Trade System.
- security_app.py: a simple Streamlit security lens over the same workbook data.

## Test
From the package directory:

    streamlit run security_app.py

The existing app.py remains in place and uses the same data folder.

## Important
This is a schema/product test, not an exhaustive PGSA or global coast-guard ingestion.
Secondary vessel-reference ownership data should be periodically reverified and made time-aware in PostgreSQL/Supabase.
