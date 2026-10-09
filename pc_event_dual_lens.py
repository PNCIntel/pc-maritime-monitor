"""P&C event intelligence panels, sourced from PostgreSQL views only.
Neither screen infers attack coordinates, risk ratings, causation or company exposure.
Call render_event_lens(db, event_id, product) inside an existing event dossier.
"""
from __future__ import annotations
import streamlit as st


def _records(db, view, event_id):
    try:
        return (db.table(view).select('*').eq('event_id', event_id)
                .limit(1).execute().data or []), None
    except Exception as exc:
        return [], str(exc)


def _items(title, records, *, limit=6):
    if not records:
        return
    with st.expander(f'{title} ({len(records)})', expanded=False):
        for row in records[:limit]:
            if isinstance(row, dict):
                # Show only meaningful, non-empty fields, not technical IDs.
                fields = [(k.replace('_', ' ').capitalize(), v) for k, v in row.items()
                          if v is not None and k not in ('event_id', 'created_at', 'updated_at', 'metadata')]
                st.write(' · '.join(f'{k}: {str(v)[:180]}' for k, v in fields[:5]))
        if len(records) > limit:
            st.caption(f'{len(records)-limit} additional records available in the source data.')


def render_event_lens(db, event_id: str, product: str):
    """Render a small, optional business-facing layer in existing event dossier.
    Does not replace the established full description, maps or sources.
    """
    view = 'pc_v6_security_events' if product == 'intelligence' else 'pc_v6_trade_event_effects'
    rows, error = _records(db, view, event_id)
    if error:
        st.caption('Supplementary assessment and effects are temporarily unavailable.')
        return
    if not rows:
        return
    r = rows[0]
    if product == 'intelligence':
        st.subheader('Threat, risk & verification')
        a, b, c = st.columns(3)
        a.metric('Assessment', str(r.get('approved_risk_level') or 'Not assessed').replace('_', ' ').title())
        b.metric('Trend', str(r.get('approved_risk_trend') or 'Not assessed').replace('_', ' ').title())
        c.metric('Verification', str(r.get('event_verification') or 'Not recorded').replace('_', ' ').title())
        if r.get('assessment_date'):
            st.caption(f"Assessment dated {r['assessment_date']} · confidence: {r.get('assessment_confidence') or 'not recorded'}")
        elif r.get('assessment_approval_status'):
            st.caption('An assessment exists but is not approved for publication as a risk rating.')
        _items('Threat categories', r.get('risk_tags'))
        _items('Observed effects', r.get('incident_impacts'))
        _items('Monitoring indicators', r.get('monitoring_observations'))
        _items('Monitoring alerts', r.get('monitoring_alerts'))
        locations = r.get('recorded_locations') or []
        if locations:
            st.caption(f'{len(locations)} recorded incident location(s); exact positions and context must remain distinct.')
    else:
        st.subheader('Trade & operational consequences')
        st.caption('Recorded business consequences only. Related facilities are not automatically direct impacts.')
        _items('Transport and logistics impacts', r.get('logistics_impacts'))
        _items('Other recorded impacts', r.get('other_impacts'))
        _items('Company effects', r.get('company_effects'))
        _items('Recorded asset connections', r.get('linked_objects'))
        if not any(r.get(k) for k in ('logistics_impacts', 'other_impacts', 'company_effects')):
            st.info('No structured commercial effect has been recorded for this event yet.')
