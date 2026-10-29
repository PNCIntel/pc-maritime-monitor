# Below the Waterline — P&C maritime intelligence

Standalone Next.js application scaffold under the existing maritime repository. **Not deployed** and **not yet connected to Supabase**. This subtree is intentionally portable to a dedicated `pc-below-the-waterline-web` repository.

## Start

```bash
cd below-the-waterline
npm install
npm run dev
```

## Product tree

- `app/page.tsx`: branded landing, search entry point, intelligence layers, priority regions and attribution.
- `app/vessels/page.tsx`: search shell; no fabricated vessel records or exposed credentials.
- `app/style.css`: royal navy/blue and muted gold visual system.
- `.env.example`: future server-side configuration placeholders only.

## Architecture guardrails

- Shared **existing** Supabase `public` canonical model. No `pc_next` or parallel entity store.
- PSC joins use canonical vessel identity and the existing PSC extension only after actual view/column verification.
- Historical vessel names/flags and dated owner, ISM, technical and commercial roles; do not infer roles from current ownership.
- Inspection, deficiencies, detention, release, bans and corrections remain distinct but linked.
- Source chain to primary originator, event-vs-inference separation, source licensing and data-as-of dates.
- Public reads must use a narrowly scoped, approved view/API with RLS and appropriate authentication. Never expose a service-role key in browser code.
- No auto-created provisional identities. Unmatched source records remain in ingestion staging.
- hormuz.now badge links to the source; PortWatch-derived reuse rights require separate verification.

## Not yet implemented

Canonical vessel search adapter, authenticated analyst/client roles, PSC API, vessel dossier, incident timeline, regional trend ingestion, report export and deployment. Those require verified production view contracts and application access design.
