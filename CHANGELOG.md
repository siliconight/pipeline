# Pipeline Changelog

Entries for v0.1.1 through v0.5.0 were RECONSTRUCTED on 2026-08-14 from this
repo's own commits, weeks after the fact. They record what each release did,
taken from the commit that bumped VERSION, and each names its sha. They do
not explain why, because nothing on disk says why -- and a made-up rationale
in the file whose job is to be the record is worse than an admitted gap.

## [v0.6.0] - guard-rail evidence stamped across the mission registry

Every mission in `mission_registry.json` gains a `guard_rails` record in its
`evidence` block:

    "guard_rails": "Site guard-rail pass (2026-07-21): cover remediation
    applied; all mission sites re-assembled, walktest + 4-player smoke
    re-verified green"

The same hunk on every site -- `ballpark_block`, `bank_tower_block`,
`brewery_block`, `central_vault`, `deli_block`, `independence_mall`,
`mainline_mansion` and the rest. 60 changed lines in the mission registry.

Also 6 lines in `building_configuration_registry.json` and 4 in `.gitignore`,
which are named here and not described: this entry was written from the
mission-registry diff on 2026-08-14, and those two were not read. A guess
about them would be the kind of thing this file exists to not contain.

WRITTEN FROM THE DIFF BECAUSE THE COMMIT SUBJECT SAYS NOTHING. `7ed8e00` is
"checkpoint: uncommitted working tree", dated 2026-08-12. On the strength of
that subject this release was passed over once already, on the reasoning that
a checkpoint is not a release. It is one; the subject was just wrong about
its own commit. A registry-wide evidence key is precisely the change this
tool is for.

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
