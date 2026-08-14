# Pipeline Changelog

Entries for v0.1.1 through v0.5.0 were RECONSTRUCTED on 2026-08-14 from this
repo's own commits, weeks after the fact. They record what each release did,
taken from the commit that bumped VERSION, and each names its sha. They do
not explain why, because nothing on disk says why -- and a made-up rationale
in the file whose job is to be the record is worse than an admitted gap.

## [v0.5.0] - 2026-07-21

Phase 4 complete. Registries at 100 configs / 36 families / 20 missions /
8 heroes, every family placed, engine evidence stamped throughout. The
`bank_job` P0 record backfilled.

Reconstructed from `79b0db3`. That commit's subject does not name a version;
it is the next commit after 0.4.0 to touch VERSION, and VERSION reads 0.5.0.
The factory manifest's note for this tool reports the same four numbers.

## [v0.4.0] - 2026-07-21

75 configs / 28 families / 12 missions / 4 heroes registered, all
engine-stamped.

Reconstructed from `b93273f`.

## [v0.3.0] - 2026-07-20

40 configs / 16 families / 6 missions registered, all engine gates stamped.

Reconstructed from `a74119a`.

## [v0.2.0] - 2026-07-19

The first registrations beyond the reference set: 10 Phase 1 configs and
2 missions, all engine gates stamped.

Reconstructed from `a4002e4`.

## [v0.1.1] - 2026-07-18

Reference records stamped PASS on all engine gates.

Reconstructed from `22b4c79`.

## [v0.1.0] - 2026-07-17

First release: the production registrar. `registry.py` owns
`building_configuration_registry.json` + `mission_registry.json` — ID grammar,
sibling-distinction rules (>=2 tactical AND >=2 visual dimensions),
approved-requires-proof enforcement, mission composition rules, automatic
config<->mission back-links, deterministic writes, and the Phase 4
`check --portfolio` acceptance sweep. 16 tests.
