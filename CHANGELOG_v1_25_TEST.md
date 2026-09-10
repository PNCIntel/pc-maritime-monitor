# v1.25 TEST — Hercules Star canonical incident-resolution test

This test pass demonstrates the full P&C entity/evidence workflow using the 9 Sep 2026 Hercules Star incident off Dubai.

Added:
- Canonical vessel HERCULES STAR (IMO 9916135)
- Peninsula, Hercules Tanker Management, and Macaw Shipping Ltd company entities
- Port Rashid as a canonical port/gateway entity
- Vessel ownership/manager/charter/fleet-affiliation relationships
- Confirmed 9 Sep 2026 incident as EVENT_0019 / OBS_000612
- News record NEWS00018 and entity links
- Retrospective link from the existing 1 Mar 2026 Hercules Star observation to the new canonical vessel
- Five source-register entries preserving provenance

Important analytical handling:
- Vessel identity is confirmed by Peninsula.
- Weapon type remains unresolved; the model preserves `unknown projectile / suspected drone` rather than upgrading it to a confirmed drone strike.
- Port Rashid is modeled as the incident reference/gateway, not as the physical incident location.
- Hercules Tanker Management is modeled as a fleet affiliation, not asserted as legal registered owner.
