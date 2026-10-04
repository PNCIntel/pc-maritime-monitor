# Port & Maritime Notice Monitor — 2026-10-04

This adds an official-source registry and first-pass notice collector to **Power Admin**.

## Install
1. Run `sql/20261004_port_notice_monitor.sql` in Supabase SQL Editor.
2. Reboot the Power Admin Streamlit app.
3. Open **Port notices**.
4. Click **Seed / refresh official starter registry**.
5. Select sources and click **Check selected official sources now**.

The starter registry covers RAK Ports, Fujairah, Singapore MPA, Rotterdam, Suez Canal Authority, Panama Canal Authority, AMSA, Transport Canada and USCG.

Discovery does **not** automatically assert a restriction against a vessel. It records the official notice and source URL first. The schema separately supports status, effective dates, supersession/cancellation, stored documents, IMO extraction and asset linking so those can be reviewed and published into the canonical graph.

The UAE Circular 5/2026 example is exactly why status history matters: an issued restriction can later be cancelled or superseded; the system must retain both observations rather than overwriting history.
