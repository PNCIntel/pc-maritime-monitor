# P&C Trade System v3.3.6 — Multimodal Regional UI

Build date: 11 Sep 2026

## Trade app
- Reworked sidebar around Domains, Entities, Alerts & Monitoring, Markets & Policy and Intelligence.
- Added unified Maritime workspace with Incidents, Disruptions, Vessels, Ports and Navigation & Compliance tabs.
- Rail now includes a Security & Disruption tab sourced from the shared event layer.
- Aviation now includes Aviation Disruptions plus linked cross-domain event coverage.
- Added Regional Maps for Global, Middle East, Africa, Europe, North America, Central America & Caribbean, South America, South Asia, Asia-Pacific, Central Asia and Arctic.
- Regional map can switch between incidents/disruptions and ports, with trade/commercial impact retained in the event table.
- Ports navigation is surfaced as Ports & Terminals while preserving the existing port-detail implementation.

## Intelligence app
- Added Regional Maps to the Intelligence Desk and expanded regional coverage to the broad commercial regions above plus Black Sea and Baltic theatre views.
- Added Rail & Inland domain intelligence.
- Added Energy & Infrastructure domain intelligence.
- Aviation & Movement now surfaces the Aviation Disruptions sheet before the wider event/aircraft view.
- Existing Maritime Security, Ports & Infrastructure, Watch Areas, Monitoring, Alerts and Sanctions/Compliance remain intact.

## Design principle
Trade and Intelligence share the same canonical events and entities. Trade emphasizes commercial exposure and movement; Intelligence emphasizes incidents, threats, escalation and operational implications.
