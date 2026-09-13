P&C Trade v3.3.41 Regional Maps Fix

Replace only app.py.

Fixes the NameError on Operating Picture > Regional Maps by restoring:
- _regional_business_security_events()
- render_regional_business_security_maps()

Based directly on app_world_bank_v3_3_40.py, so the World Bank macro changes are retained.
No SQL changes required.
