# v3.0.8 — Watch Areas + PortWatch

P&C Intelligence Watch Areas now behaves as an intelligence brief: current picture, confidence, horizon, priority indicators, change thresholds, recent activity, exposed ports/inland hubs and related disruption watches.

P&C Trade Watch Areas no longer uses `Open corridor context`. A disruption can be selected and expanded into status, probability/read, time horizon, mode impact, trade/commercial impact, trigger and connected canonical trade exposure.

P&C Trade Ports now includes a live IMF PortWatch block for the selected canonical port. It attempts a conservative same-country name match, shows the latest available day (port calls, container calls, tanker calls, imports, exports), and shows a 30-observation trend when available. PortWatch remains an on-demand operational layer and is not written back into Excel.

No canonical data was forked.
