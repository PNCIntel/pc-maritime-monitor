# P&C Trade v3.3.49 — Search & MARSEC Stability Fix

Replace only `app.py`.

Changes:
- fixes MARSEC/Maritime TypeError caused by nullable/mixed values in filter option generation;
- replaces unsafe unique/sort filter construction in several workspaces with the shared safe search helper;
- Maritime Overview now counts the live/merged commercial vessel set instead of a stale legacy table;
- Maritime > Vessels now has company/group/IMO/owner/operator search and fleet expansion;
- Maritime > Ports now supports port/country/company/operator search and filters;
- no SQL changes required.
