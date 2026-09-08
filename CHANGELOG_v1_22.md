# P&C Trade System v1.22 — Map Restoration

## Restored / added
- Restored geographic map views without removing the v1.21 human-readable display layer.
- Operating Picture: recent geolocated event map.
- Ports & Terminals: selected-port map using canonical port coordinates.
- News & Events: map of filtered geolocated event observations.
- Rail Networks: map of rail-linked ports where the current model contains coordinates.
- Ferry Systems: ferry-terminal network map.
- Watch Areas: gateway-port map for the selected corridor/watch area.

## Data discipline
- Maps plot only coordinates already present in the model.
- No synthetic or inferred coordinates are created for entities lacking latitude/longitude.
- Internal IDs remain available for joins but are not required in map presentation.

## Build
- Sidebar build label updated to APP BUILD v1.22.
