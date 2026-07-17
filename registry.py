#!/usr/bin/env python3
"""
registry.py  --  building-configuration & mission registrar
===========================================================
The registries are the production system's source of truth for WHAT IS
APPROVED and WHY IT WAS ALLOWED TO BE. Two files:

    building_configuration_registry.json
    mission_registry.json

This tool is the only supported way to write them. It refuses records that
violate the Production Package's registry rules (§20, §21, acceptance 41-43):

  * duplicate IDs
  * malformed IDs (configs: BLD_<FAMILY>_<letter><2 digits>, e.g.
    BLD_BANK_BRANCH_A03; missions: MSN_<NAME>_<2 digits>)
  * a record marked approved while a blocking gate failed
  * approved records with missing output/proof references (paths must exist)
  * approved configs whose visual score < 4 (standard) — hero average < 4.5
    is checked at the mission level
  * sibling configurations (same family) that do not differ in >= 2 tactical
    AND >= 2 visual dimensions (§6/§7, encoded as dimension->value tags from
    the allowed vocabularies)
  * missions that reference unregistered configuration IDs
  * two missions using the identical full set of configuration IDs
  * a family placed in > 4 missions without `overuse_approved`

Usage:
    python registry.py init --dir <registry_dir>
    python registry.py add-config  record.json [--dir DIR] [--root ROOT]
    python registry.py add-mission record.json [--dir DIR] [--root ROOT]
    python registry.py check [--dir DIR] [--root ROOT] [--portfolio]

`--root` is the path proof references are resolved against (default: the
registry dir). `check --portfolio` additionally applies the whole-library
acceptance targets (36 families / 100 configs / 20 missions / 50 placements /
every family used) — expected to fail until Phase 4, so it is a separate flag.

Deterministic: records are stored sorted by ID; writing the same content twice
is byte-identical.
"""

import argparse
import json
import os
import re
import sys

CONFIG_ID = re.compile(r"^BLD_[A-Z0-9]+(?:_[A-Z0-9]+)*_[A-Z]\d{2}$")
MISSION_ID = re.compile(r"^MSN_[A-Z0-9]+(?:_[A-Z0-9]+)*_\d{2}$")

# §6 valid tactical dimensions (kebab-case keys)
TACTICAL_DIMENSIONS = {
    "attacker_entrance_count", "attacker_entrance_location",
    "defender_spawn_location", "objective_room_location",
    "extraction_facing_route", "vertical_traversal_route",
    "stair_placement", "ladder_placement", "breach_point_placement",
    "window_sightline_placement", "interior_route_graph",
    "chokepoint_placement", "cover_arrangement",
    "secure_room_access_pattern", "public_to_secure_transition",
    "rooftop_access", "basement_access", "service_entrance_placement",
}

# §7 valid visual dimensions
VISUAL_DIMENSIONS = {
    "architectural_theme", "facade_module_family", "roof_silhouette",
    "window_family", "doorway_family", "material_package",
    "signage_package", "prop_habitat", "interior_business_identity",
    "wear_state", "damage_state", "exterior_dressing_package",
    "regional_construction_style", "security_level", "age_of_construction",
    "renovation_state",
}

CONFIG_REQUIRED = [
    "configuration_id", "building_family", "status", "spec_path", "seed",
    "gameplay_profile", "tactical_tags", "visual_tags", "zoo_theme",
]
CONFIG_PROOF_PATHS = [
    # path fields that must exist on disk for an APPROVED record
    "spec_path", "glb_path", "gameplay_path", "slots_path", "manifest_path",
    "kit_manifest_path", "review_sheet_path",
    "validation_report_path", "combat_audit_path", "navigation_report_path",
    "roundtrip_report_path",
]
CONFIG_GATES = [
    # result fields that must be exactly "pass" for an APPROVED record
    "structural_validation", "navigation_validation", "coordinate_validation",
    "runtime_walktest",
]

MISSION_REQUIRED = [
    "mission_id", "name", "classification", "lot_spec_path",
    "configuration_ids", "objective_building",
]
MISSION_GATES = [
    "site_validation", "connectivity_validation", "tactical_validation",
    "godot_import", "multiplayer_smoke_test",
]

STATUSES = ("draft", "candidate", "approved", "retired")

BUILDINGS_FILE = "building_configuration_registry.json"
MISSIONS_FILE = "mission_registry.json"


class RegistryError(Exception):
    pass


# ---------------------------------------------------------------------------
# io
# ---------------------------------------------------------------------------

def _load(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save(path, payload):
    payload["records"] = sorted(payload["records"],
                                key=lambda r: r.get(payload["key"], ""))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
        f.write("\n")


def _empty(kind):
    key = "configuration_id" if kind == "buildings" else "mission_id"
    return {"registry": kind, "schema_version": 1, "key": key, "records": []}


def load_registries(reg_dir):
    b = _load(os.path.join(reg_dir, BUILDINGS_FILE), _empty("buildings"))
    m = _load(os.path.join(reg_dir, MISSIONS_FILE), _empty("missions"))
    return b, m


# ---------------------------------------------------------------------------
# record validation
# ---------------------------------------------------------------------------

def _fail(errs, msg):
    errs.append(msg)


def validate_config(rec, siblings, root, errs):
    cid = rec.get("configuration_id", "")
    if not CONFIG_ID.match(cid or ""):
        _fail(errs, f"config id '{cid}' does not match "
                    f"BLD_<FAMILY>_<letter><2 digits> (e.g. BLD_BANK_BRANCH_A03)")
    for f in CONFIG_REQUIRED:
        if rec.get(f) in (None, "", [], {}):
            _fail(errs, f"{cid}: required field '{f}' missing/empty")
    status = rec.get("status")
    if status not in STATUSES:
        _fail(errs, f"{cid}: status '{status}' not one of {STATUSES}")

    fam = rec.get("building_family", "")
    if cid and fam and not cid.startswith(f"BLD_{fam.upper()}_"):
        _fail(errs, f"{cid}: id does not embed its building_family '{fam}'")

    for tag_field, allowed, label in (
            ("tactical_tags", TACTICAL_DIMENSIONS, "tactical"),
            ("visual_tags", VISUAL_DIMENSIONS, "visual")):
        tags = rec.get(tag_field) or {}
        if not isinstance(tags, dict):
            _fail(errs, f"{cid}: {tag_field} must be a dict of "
                        f"dimension -> value")
            continue
        bad = set(tags) - allowed
        if bad:
            _fail(errs, f"{cid}: unknown {label} dimension(s): {sorted(bad)} "
                        f"(see §6/§7 vocab in registry.py)")

    # sibling distinction: >=2 tactical AND >=2 visual dimensions must differ
    for sib in siblings:
        if sib.get("configuration_id") == cid:
            continue
        for tag_field, label in (("tactical_tags", "tactical"),
                                 ("visual_tags", "visual")):
            a = rec.get(tag_field) or {}
            b = sib.get(tag_field) or {}
            diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
            if len(diff) < 2:
                _fail(errs, f"{cid}: differs from sibling "
                            f"'{sib.get('configuration_id')}' in only "
                            f"{len(diff)} {label} dimension(s); the Production "
                            f"Package requires >= 2 (§{'6' if label == 'tactical' else '7'})")

    if status == "approved":
        for f in CONFIG_GATES:
            if rec.get(f) != "pass":
                _fail(errs, f"{cid}: approved but gate '{f}' = "
                            f"{rec.get(f)!r} (must be 'pass')")
        score = rec.get("visual_quality_score")
        if not isinstance(score, (int, float)) or score < 4:
            _fail(errs, f"{cid}: approved but visual_quality_score = "
                        f"{score!r} (standard configs need >= 4)")
        open_issues = rec.get("open_issues") or []
        blocking = [i for i in open_issues
                    if i.get("severity") in ("blocking", "high")]
        if blocking:
            _fail(errs, f"{cid}: approved with unresolved "
                        f"blocking/high issue(s): "
                        f"{[i.get('title') for i in blocking]}")
        med = [i for i in open_issues if i.get("severity") == "medium"]
        if len(med) > 5:
            _fail(errs, f"{cid}: approved with {len(med)} unresolved medium "
                        f"issues (limit 5)")
        for i in med:
            if i.get("affects") in ("navigation", "collision", "coordinates"):
                _fail(errs, f"{cid}: approved with a medium issue affecting "
                            f"{i.get('affects')} ('{i.get('title')}') — "
                            f"§18 forbids this")
        for f in CONFIG_PROOF_PATHS:
            p = rec.get(f)
            if not p:
                _fail(errs, f"{cid}: approved but proof reference '{f}' "
                            f"is missing")
            elif root and not os.path.exists(os.path.join(root, p)):
                _fail(errs, f"{cid}: approved but proof file does not exist: "
                            f"{f} -> {p}")
        if not rec.get("approval_owner") or not rec.get("approval_date"):
            _fail(errs, f"{cid}: approved without approval_owner/approval_date")


def validate_mission(rec, configs_by_id, all_missions, root, errs):
    mid = rec.get("mission_id", "")
    if not MISSION_ID.match(mid or ""):
        _fail(errs, f"mission id '{mid}' does not match MSN_<NAME>_<2 digits>")
    for f in MISSION_REQUIRED:
        if rec.get(f) in (None, "", [], {}):
            _fail(errs, f"{mid}: required field '{f}' missing/empty")
    if rec.get("classification") not in ("standard", "hero"):
        _fail(errs, f"{mid}: classification must be 'standard' or 'hero'")
    status = rec.get("status", "draft")
    if status not in STATUSES:
        _fail(errs, f"{mid}: status '{status}' not one of {STATUSES}")

    cids = rec.get("configuration_ids") or []
    n = len(cids)
    lo, hi = (2, 4) if rec.get("classification") == "hero" else (1, 3)
    if cids and not (lo <= n <= hi):
        _fail(errs, f"{mid}: {rec.get('classification')} missions use "
                    f"{lo}-{hi} buildings, got {n}")
    for cid in cids:
        if cid not in configs_by_id:
            _fail(errs, f"{mid}: references unregistered configuration "
                        f"'{cid}' (orphaned reference)")
        elif status == "approved" and \
                configs_by_id[cid].get("status") != "approved":
            _fail(errs, f"{mid}: approved mission uses non-approved "
                        f"configuration '{cid}'")

    combo = frozenset(cids)
    for other in all_missions:
        if other.get("mission_id") == mid:
            continue
        if combo and frozenset(other.get("configuration_ids") or []) == combo:
            _fail(errs, f"{mid}: uses the same complete configuration "
                        f"combination as '{other.get('mission_id')}' "
                        f"(§9 forbids duplicate combos)")

    if status == "approved":
        for f in MISSION_GATES:
            if rec.get(f) != "pass":
                _fail(errs, f"{mid}: approved but gate '{f}' = "
                            f"{rec.get(f)!r} (must be 'pass')")
        if rec.get("classification") == "hero":
            scores = rec.get("hero_visual_scores") or []
            if len(scores) < 2:
                _fail(errs, f"{mid}: hero mission needs visual scores from "
                            f">= 2 reviewers, got {len(scores)}")
            elif sum(scores) / len(scores) < 4.5:
                _fail(errs, f"{mid}: hero visual average "
                            f"{sum(scores)/len(scores):.2f} < 4.5")
        p = rec.get("lot_spec_path")
        if p and root and not os.path.exists(os.path.join(root, p)):
            _fail(errs, f"{mid}: approved but lot_spec_path does not exist: {p}")
        if not rec.get("approval_owner") or not rec.get("approval_date"):
            _fail(errs, f"{mid}: approved without approval_owner/approval_date")


def validate_cross(breg, mreg, errs, portfolio=False):
    configs = breg["records"]
    missions = mreg["records"]
    by_id = {}
    for r in configs:
        cid = r.get("configuration_id")
        if cid in by_id:
            _fail(errs, f"duplicate configuration id '{cid}'")
        by_id[cid] = r
    mids = set()
    for r in missions:
        mid = r.get("mission_id")
        if mid in mids:
            _fail(errs, f"duplicate mission id '{mid}'")
        mids.add(mid)

    # family overuse: > 4 missions without approval
    fam_missions = {}
    for m in missions:
        fams = {by_id[c]["building_family"] for c in
                (m.get("configuration_ids") or []) if c in by_id}
        for f in fams:
            fam_missions.setdefault(f, set()).add(m.get("mission_id"))
    for fam, used in sorted(fam_missions.items()):
        if len(used) > 4:
            offenders = [m for m in missions
                         if m.get("mission_id") in used
                         and not m.get("overuse_approved")]
            if offenders:
                _fail(errs, f"family '{fam}' appears in {len(used)} missions "
                            f"(> 4) without overuse_approved on: "
                            f"{[m.get('mission_id') for m in offenders]}")

    # configurations must record which missions use them, and vice versa
    for m in missions:
        for c in m.get("configuration_ids") or []:
            if c in by_id:
                listed = by_id[c].get("missions") or []
                if m.get("mission_id") not in listed:
                    _fail(errs, f"config '{c}' does not list mission "
                                f"'{m.get('mission_id')}' in its missions[] "
                                f"(registry must match outputs)")

    if portfolio:
        fams = {r.get("building_family") for r in configs}
        approved = [r for r in configs if r.get("status") == "approved"]
        appr_m = [m for m in missions if m.get("status") == "approved"]
        placements = sum(len(m.get("configuration_ids") or [])
                         for m in appr_m)
        heroes = [m for m in appr_m if m.get("classification") == "hero"]
        if len(fams) != 36:
            _fail(errs, f"portfolio: {len(fams)} families, target exactly 36")
        if len(approved) != 100:
            _fail(errs, f"portfolio: {len(approved)} approved configurations, "
                        f"target exactly 100")
        if len(appr_m) != 20:
            _fail(errs, f"portfolio: {len(appr_m)} approved missions, "
                        f"target exactly 20")
        if len(heroes) != 8:
            _fail(errs, f"portfolio: {len(heroes)} hero missions, target 8")
        if placements < 50:
            _fail(errs, f"portfolio: {placements} building placements, "
                        f"target >= 50")
        used_fams = set()
        for m in appr_m:
            for c in m.get("configuration_ids") or []:
                if c in by_id:
                    used_fams.add(by_id[c]["building_family"])
        unused = fams - used_fams
        if unused:
            _fail(errs, f"portfolio: families never placed in a mission: "
                        f"{sorted(unused)}")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def check_all(reg_dir, root=None, portfolio=False):
    root = root or reg_dir
    breg, mreg = load_registries(reg_dir)
    errs = []
    by_fam = {}
    for r in breg["records"]:
        by_fam.setdefault(r.get("building_family"), []).append(r)
    by_id = {r.get("configuration_id"): r for r in breg["records"]}
    for r in breg["records"]:
        validate_config(r, by_fam.get(r.get("building_family"), []), root, errs)
    for r in mreg["records"]:
        validate_mission(r, by_id, mreg["records"], root, errs)
    validate_cross(breg, mreg, errs, portfolio=portfolio)
    return errs


def add_record(reg_dir, kind, rec_path, root=None):
    root = root or reg_dir
    with open(rec_path, "r", encoding="utf-8") as f:
        rec = json.load(f)
    breg, mreg = load_registries(reg_dir)
    reg, fname = ((breg, BUILDINGS_FILE) if kind == "config"
                  else (mreg, MISSIONS_FILE))
    key = reg["key"]
    rid = rec.get(key)
    if not rid:
        raise RegistryError(f"record has no {key}")
    existing = [r for r in reg["records"] if r.get(key) != rid]
    replaced = len(existing) != len(reg["records"])
    reg["records"] = existing + [rec]

    # the registrar owns config<->mission back-links: recompute every
    # config's missions[] from the mission records (single source of truth)
    uses = {}
    for m in mreg["records"]:
        for c in m.get("configuration_ids") or []:
            uses.setdefault(c, []).append(m.get("mission_id"))
    for r in breg["records"]:
        r["missions"] = sorted(uses.get(r.get("configuration_id"), []))

    # validate the WHOLE registry with the new record in place
    errs = []
    if kind == "config":
        by_fam = {}
        for r in breg["records"]:
            by_fam.setdefault(r.get("building_family"), []).append(r)
        for r in breg["records"]:
            validate_config(r, by_fam.get(r.get("building_family"), []),
                            root, errs)
        by_id = {r.get("configuration_id"): r for r in breg["records"]}
        for r in mreg["records"]:
            validate_mission(r, by_id, mreg["records"], root, errs)
    else:
        by_id = {r.get("configuration_id"): r for r in breg["records"]}
        for r in mreg["records"]:
            validate_mission(r, by_id, mreg["records"], root, errs)
    validate_cross(breg, mreg, errs)
    if errs:
        raise RegistryError(
            f"refusing to register '{rid}':\n  " + "\n  ".join(errs))
    # back-link maintenance touches the buildings registry on every mission
    # write, so persist both files — they are one consistent unit.
    _save(os.path.join(reg_dir, BUILDINGS_FILE), breg)
    _save(os.path.join(reg_dir, MISSIONS_FILE), mreg)
    return rid, replaced


def main(argv=None):
    ap = argparse.ArgumentParser(description="production registrar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("--dir", default=".")
    for c in ("add-config", "add-mission"):
        p = sub.add_parser(c)
        p.add_argument("record")
        p.add_argument("--dir", default=".")
        p.add_argument("--root", default=None)
    p = sub.add_parser("check")
    p.add_argument("--dir", default=".")
    p.add_argument("--root", default=None)
    p.add_argument("--portfolio", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "init":
        os.makedirs(args.dir, exist_ok=True)
        for fname, kind in ((BUILDINGS_FILE, "buildings"),
                            (MISSIONS_FILE, "missions")):
            path = os.path.join(args.dir, fname)
            if not os.path.exists(path):
                _save(path, _empty(kind))
                print(f"[registry] created {path}")
            else:
                print(f"[registry] exists {path}")
        return 0

    if args.cmd in ("add-config", "add-mission"):
        kind = "config" if args.cmd == "add-config" else "mission"
        try:
            rid, replaced = add_record(args.dir, kind, args.record, args.root)
        except RegistryError as ex:
            print(f"[registry] REFUSED: {ex}", file=sys.stderr)
            return 1
        print(f"[registry] {'updated' if replaced else 'registered'} {rid}")
        return 0

    if args.cmd == "check":
        errs = check_all(args.dir, args.root, portfolio=args.portfolio)
        if errs:
            print(f"[registry] {len(errs)} problem(s):")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("[registry] registries are coherent")
        return 0


if __name__ == "__main__":
    sys.exit(main())
