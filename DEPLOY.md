# P&C Delivery Network v5 — Trade + Security

## Scope
Additive SQL plus targeted Python changes to the **existing** richly formatted dossiers. No new raw-record UI. Applies to **all fixed infrastructure**, not one port. Uses reviewed identity aliases and preserves original record IDs. v5 connected edges draw from generic asset relationships and specialist parent-terminal relationships; company roles from existing asset/entity graph and direct operator fields. **No location guessing**; missing coordinates remain missing.

## Deploy
1. Run `sql/20261009_network_delivery_v5.sql` in Supabase **after** preferred identity functions and earlier v4 intelligence views.
2. In a **test branch**, overlay `pc_terminal.py`, `pc_market_lenses.py` and `pc_prepared_bridge.py`. Other files in this package are baseline references; retain all other repository modules (`pc_drilldown`, `pc_corporate_network`, `shared.pc_db`, etc.).
3. Restart both Streamlit applications and clear their cached data.
4. Search Fujairah / `PORTG0046` and the verified Port of Fujairah. Both should display the preferred enriched profile; repeat for unrelated ports and a rail/airport to ensure no accidental port-only assumptions.
5. Verify with SQL below. Expect six terminal child IDs plus **additional commercial connections** when present. Six terminal records are not necessarily six distinct physical terminals.

```sql
SELECT child_asset_id, connected_name, relationship_labels
FROM public.pc_v5_infrastructure_connections
WHERE parent_asset_id = 'PORT_UAE_PORT_OF_FUJAIRAH'
ORDER BY connected_name;
SELECT company_name, role FROM public.pc_v5_infrastructure_companies
WHERE asset_id = 'PORT_UAE_PORT_OF_FUJAIRAH';
```

## Known limits
This is an integration fix, not a completed network visualization. Parent asset coordinates are absent in current Fujairah records. Event linkage only uses existing linked evidence. Generic asset links may include adjacent independent facilities, which are labelled by original relationship and **must not be counted as owned terminals**. Live Supabase integration not tested. The corporate-network performance work is not in scope.
