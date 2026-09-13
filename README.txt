P&C Workflow 038 — One-Pass AI Research: Transactions + Routes

Install after Workflow 037.

This patch permanently incorporates the final fixes proven on the fresh
multisource document + web AI Research acceptance job:
- transaction promotion into pc_transactions
- boolean-safe operating_control
- explicit million/billion/trillion transaction value scaling
- route promotion into pc_transport_routes
- required route mode inference
- corrected UUID typing in canonical-name alias registration
- pc_reconcile_ingestion_job_v2 now calls transactions and routes before QA

No Admin app replacement is required for this SQL patch.
