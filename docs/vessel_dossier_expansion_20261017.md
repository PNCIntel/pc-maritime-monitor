# Vessel dossier expansion — inventory and reconciliation queue

This change is the first UI repair for the existing single-model vessel profile: historical company roles now render as navigable entity records, alongside their source/period notes, rather than as a dead-end dataframe. It does not assert unverified roles as current.

## Reference cases to reconcile with the live DB
- DF PEAK (IMO 9341067): already displays linked current roles and a three-name identity history.
- ST HELENA (IMO 8716306): has dated/history company data, but lacks populated identity-name history and resolved current roles.
- SMYRTOS: confirm IMO from authoritative register and reuse existing record, if any.

## Extended discovery queue (not claims of import or designation)
France/UK/Belgium: GRINCH, BORACAY/PUSHPA, DEYNA, TAGOR, DELIVER, ETHERA, FORWARDER, VIRA 1.
Black Sea: KAIROS, VIRAT, WINE TRADER, YARA J.
Baltic: EAGLE S, YI PENG 3, VEZHEN, SILVER DANIA.
Taiwan: SHUNXING 39, HONG TAI 58.
Regional conflict: ST HELENA, GFS PRIDE.

## Per-hull acceptance criteria
1. Resolve vessel by verified IMO first; alias/name changes are history on one hull, not duplicates.
2. Record historical names with source observation date vs actual rename date.
3. Link registered owner, beneficial owner, commercial/ISM manager, operator, charterer and broker as separately sourced, dated roles.
4. Show each resolvable company as a clickable linked P&C entity in Overview and Ownership & Management.
5. Link incidents with relationship type, evidence and confidence; potential incident-to-vessel matches stay potential.
6. Link ports, infrastructure, geographic areas, journeys and material impact only where evidence supports it.
7. Attach official jurisdiction-specific sanctions instruments when matched by identifiers; do not inherit designations via association.
8. Reuse the one shared P&C model and existing application read views. No parallel tables or bulk seed inserts without live-schema reconciliation.
9. Display meaningful editorial copy before boilerplate disclaimers; keep source qualifications accessible.
10. Validate mobile layout and regression-test DF PEAK, ST HELENA and SMYRTOS.

## Follow-up work
- Confirm schema and actual live coverage for each named hull and company, then prepare idempotent evidence-backed incremental SQL.
- ST HELENA: recover RMS ST HELENA / MNG TAHITI alias evidence; link to existing IMO 8716306, not a new vessel.
- Normalize redundant company-role rows only after checking whether they carry independent evidence.
- Render a source-linked chronology and appropriate asset/infrastructure relationships.
- Test in an isolated branch before merging.
