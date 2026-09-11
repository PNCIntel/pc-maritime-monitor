# P&C Trade System v3.3.4 — Marine Insight intake update

Date: 11 September 2026

This release folds the user-supplied Marine Insight Daily Newsletter PDF into the existing canonical model rather than creating a separate news silo.

## Added / updated
- 15 Marine Insight news-registry records and source records.
- Canonical event records for Caribbean counter-narcotics strike, Norway/Arctic ship seizure, IRGC tanker threat at Kuwait/Bahrain ports, Glen Sannox methane release, Finland cable-damage trial, Dubai Tower Arctic passage, U.S. Navy microreactor plan, June Aster ferry fire and ORV Sagar Manthan launch.
- New vessel seeds: Glen Sannox, Dubai Tower, June Aster and ORV Sagar Manthan.
- Defence vessel seed: Admiral Essen; existing Black Sea observation retained and not duplicated as a new canonical attack until date/details are reconciled.
- Manila South Harbour: six hybrid RTG cranes added to Port Equipment and Port News; existing terminal-expansion event remains canonical.
- Naftogaz and SEA-LNG added to the core entity registry as named source entities.

## Data-quality rule
The supplied newsletter does not expose the underlying story URLs, IMO numbers or exact coordinates. Those fields are deliberately left blank and flagged for follow-up verification rather than inferred. Existing canonical records are linked where possible to avoid duplicate incidents.
