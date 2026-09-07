POWER & CORRIDORS TRADE SYSTEM APP v4.8 — MODEL v1.12 INTEGRATED LOGISTICS
Verified: 2026-09-07

PURPOSE
-------
This release extends the P&C trade-system model beyond maritime, port and infrastructure
intelligence into integrated multimodal logistics. DHL, FedEx, Amazon and Aramex/ADQ are
modeled as connected corporate and operating ecosystems across air, ocean, rail, road,
warehousing, free zones, express, contract logistics and distribution.

MODEL SCALE
-----------
172 canonical companies / platforms
98 canonical assets
358 canonical vessels
92 corporate relationships
625 vessel relationships
316 sources
87 research-queue records
49 fleet / network portfolio records
13 aircraft type / operator records
13 logistics-real-estate records
34 infrastructure-connection edges
13 integrated-logistics network rows

NEW MODEL / RUNTIME TABLE
-------------------------
integrated_logistics_networks.csv

NEW / EXPANDED COMPANY ECOSYSTEMS
---------------------------------
DHL AG
- DHL Express
- DHL Global Forwarding
- DHL Supply Chain
- DHL eCommerce
- Deutsche Post AG
- DHL Aviation network

FedEx
- FedEx Corporation
- Federal Express Corporation
- FedEx Supply Chain
- FedEx Freight Holding Company (independent after 1 Jun 2026)

Amazon
- Amazon.com, Inc.
- Amazon Supply Chain Services
- Amazon Global Logistics
- Amazon Freight
- Amazon Air
- Sun Country cargo-operating relationship

Aramex / ADQ
- ADQ
- Q Logistics Holding LLC
- Aramex PJSC
- AD Ports Group ownership connection

DATA-INTEGRITY RULES
--------------------
1. Amazon service brands are modeled as business platforms unless a separate legal entity
   is established by evidence.
2. DHL Aviation is a network / platform, not one legal airline.
3. Aircraft owner, lessor, legal operator, cargo principal and network brand remain separate.
4. FedEx Freight is independent after 1 Jun 2026; FedEx's retained 19.9% stake is not control.
5. FedEx Supply Chain remains a FedEx company until the CMA CGM transaction actually closes.
6. ADQ's 63.16% Aramex ownership is aggregate and includes the AD Ports stake; do not
   double-count the same shares.
7. Aggregate network counts do not imply individual aircraft / truck / trailer capture.

DEPLOYMENT FILES
----------------
app.py
requirements.txt
data/                              (121 CSV files in this package)
.streamlit/config.toml
.streamlit/secrets.toml.example    (example only; never commit a real key)
PC_Trade_System_Intelligence_Model_v1_12_MASTER.xlsx
manifest.json
verify_deployment.py
DEPLOYMENT-CHECKLIST.txt

STREAMLIT DEPLOYMENT
--------------------
1. Put the CONTENTS of this folder at the root of the GitHub repository used by Streamlit.
2. In Streamlit Community Cloud, set Main file path to: app.py
3. Python 3.13 is recommended.
4. The app works without OpenAI credentials. Local retrieval and evidence search remain active.
5. To enable AI synthesis in Ask P&C, add OPENAI_API_KEY in Streamlit App Settings -> Secrets.
6. Do not upload a real .streamlit/secrets.toml file to a public repository.

KEY PAGES TO TEST AFTER DEPLOYMENT
----------------------------------
Operating Picture
Ask P&C
Companies
Integrated Logistics
Vessels & Fleets
Ferry Systems
Great Lakes System
Infrastructure & Inland Logistics
Events & Disruptions
Weather & Labour

The Integrated Logistics page should expose DHL, FedEx, Amazon and Aramex/ADQ network layers,
then connect them back to assets, aircraft/fleet summaries, investments, strategic events,
real estate and corporate relationships.
