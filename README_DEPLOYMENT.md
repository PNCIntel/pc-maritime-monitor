# P&C Intelligence — COMPLETE deployment setup
10 September 2026

## Exact GitHub structure

/
├── pc_intelligence_app.py
├── requirements.txt
├── .streamlit/
│   └── config.toml
└── data/
    ├── 01_core_entities.xlsx
    ├── 02_maritime.xlsx
    ├── 05_aviation.xlsx
    ├── 06_infrastructure.xlsx
    ├── 09_intelligence.xlsx
    ├── 10_sources_evidence.xlsx
    ├── 13_events_hazards.xlsx
    └── 14_trade_policy_compliance.xlsx

The code uses:
    ROOT = Path(__file__).resolve().parent
    DATA = ROOT / "data"

Therefore the Excel files MUST be inside /data. They must not be at repo root.

## Streamlit Community Cloud

App URL:
    https://pc-intelligence.streamlit.app/

Main file path:
    pc_intelligence_app.py

## Current dataset check

13_events_hazards.xlsx should contain:
    Events: 45
    Event Locations: 48
    Latest event date: 2026-09-10

The current workbook includes Jazan/Jizan, Qeshm/Sirik/Minab/Taif,
Hormuz tanker attacks, Sea of Azov Natra/Zirkon and Novorossiysk.

## What to do in GitHub

Do not selectively upload only one workbook this time.

1. Replace pc_intelligence_app.py.
2. Replace the entire /data contents with the eight files from this package.
3. Confirm there are no duplicate '(1)' or '_LATEST' files being used instead.
4. Commit.
5. In Streamlit Community Cloud, reboot/redeploy the app if needed.
6. Open Data status.
7. It must say:
       Events loaded: 45
       Mapped location records: 48
       Latest event date: 2026-09-10
       Current 10 Sep security dataset loaded.

If it says 29 events, Streamlit is still running the old /data/13_events_hazards.xlsx.

## Regional Security checks

Middle East / Gulf:
- Jazan/Jizan is an explicit region term.
- Red Sea/Bab el-Mandeb are included.
- Map auto-fits all mapped points.

Black Sea:
- Black Sea / Sea of Azov / Azov
- Russia / Ukraine / Azerbaijan
- Odesa / Odessa
- Crimea / Sevastopol
- Novorossiysk
- Kerch / Taganrog / Mariupol / Berdyansk

## Optional tables

The previous app attempted to load four sheets which are not present in the
current Excel model:
- 09_intelligence.xlsx / Security Product View
- 14_trade_policy_compliance.xlsx / Compliance Regimes
- 14_trade_policy_compliance.xlsx / Compliance Designations
- 14_trade_policy_compliance.xlsx / Compliance Exposure

This deployment does not pretend those sheets exist. Their variables are
explicitly empty until we add those normalized tables later.
