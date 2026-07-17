# Pipeline Changelog

## [v0.1.0] - 2026-07-17

First release: the production registrar. `registry.py` owns
`building_configuration_registry.json` + `mission_registry.json` — ID grammar,
sibling-distinction rules (>=2 tactical AND >=2 visual dimensions),
approved-requires-proof enforcement, mission composition rules, automatic
config<->mission back-links, deterministic writes, and the Phase 4
`check --portfolio` acceptance sweep. 16 tests.
