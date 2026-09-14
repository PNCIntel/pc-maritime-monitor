P&C Trade v3.3.44 — Complete Entity Graph Roll-up

Replace only app.py.
No SQL changes required.

Fixes company/entity profiles so canonical relationships are read in both directions.
Profiles now include all pc_relationships touching the selected company/group scope, and
pull related pc_assets / pc_mobile_assets whether the company is the source or target
of the relationship. Direct owner/operator/manager foreign keys remain supported.

This addresses empty or partial profiles for Port of Long Beach, DP World, AD Ports Group,
Matson and other entities where canonical relationships were stored in mixed directions.
