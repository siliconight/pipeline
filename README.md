# Pipeline — the production registrar

The Production Package's source of truth for WHAT IS APPROVED AND WHY.
A standalone tool repo in the gabagool_factory pattern: own semver, own git,
gitignored by the factory repo.

    python registry.py init --dir registries
    python registry.py add-config  record.json --dir registries --root <repo root>
    python registry.py add-mission record.json --dir registries --root <repo root>
    python registry.py check --dir registries [--portfolio]

`registries/` holds the live registries (committed — they are coordination
data, not build artifacts). The registrar refuses records that violate the
Production Package §20/§21 rules; `check --portfolio` applies the Phase 4
whole-library acceptance targets and is expected to fail until then.

Tests: `python -m pytest tests/`
