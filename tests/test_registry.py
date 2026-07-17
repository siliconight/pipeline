"""Registrar tests: every §20/§21 refusal rule has a case proving it refuses,
and a well-formed record round-trips."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import registry as R


def _cfg(cid="BLD_BANK_BRANCH_A01", **over):
    rec = {
        "configuration_id": cid,
        "building_family": "BANK_BRANCH",
        "status": "draft",
        "spec_path": "specs/bank_a01.json",
        "seed": 1999,
        "gameplay_profile": "pvp_heist",
        "tactical_tags": {"objective_room_location": "basement",
                          "attacker_entrance_count": "3"},
        "visual_tags": {"architectural_theme": "delco_brick",
                        "wear_state": "worn"},
        "zoo_theme": "delco",
    }
    rec.update(over)
    return rec


def _msn(mid="MSN_BANK_JOB_01", cids=("BLD_BANK_BRANCH_A01",), **over):
    rec = {
        "mission_id": mid,
        "name": "Bank Job",
        "classification": "standard",
        "status": "draft",
        "lot_spec_path": "sites/bank_job.json",
        "configuration_ids": list(cids),
        "objective_building": "bank",
    }
    rec.update(over)
    return rec


def _write(tmp_path, rec, name="rec.json"):
    p = tmp_path / name
    p.write_text(json.dumps(rec))
    return str(p)


@pytest.fixture
def reg(tmp_path):
    d = str(tmp_path / "reg")
    R.main(["init", "--dir", d])
    return d


def test_init_and_add_config(reg, tmp_path):
    assert R.main(["add-config", _write(tmp_path, _cfg()), "--dir", reg]) == 0
    b, _ = R.load_registries(reg)
    assert len(b["records"]) == 1


def test_bad_config_id_refused(reg, tmp_path):
    rc = R.main(["add-config",
                 _write(tmp_path, _cfg(cid="BANK-A3")), "--dir", reg])
    assert rc == 1


def test_id_must_embed_family(reg, tmp_path):
    rc = R.main(["add-config",
                 _write(tmp_path, _cfg(cid="BLD_PAWN_SHOP_A01")), "--dir", reg])
    assert rc == 1


def test_duplicate_id_is_update_not_dup(reg, tmp_path):
    R.main(["add-config", _write(tmp_path, _cfg()), "--dir", reg])
    R.main(["add-config", _write(tmp_path, _cfg(seed=7)), "--dir", reg])
    b, _ = R.load_registries(reg)
    assert len(b["records"]) == 1 and b["records"][0]["seed"] == 7


def test_unknown_dimension_refused(reg, tmp_path):
    bad = _cfg()
    bad["tactical_tags"] = {"chair_position": "left", "wall_color": "red"}
    assert R.main(["add-config", _write(tmp_path, bad), "--dir", reg]) == 1


def test_sibling_distinction_enforced(reg, tmp_path):
    R.main(["add-config", _write(tmp_path, _cfg()), "--dir", reg])
    # sibling differs in only ONE tactical dimension -> refused
    sib = _cfg(cid="BLD_BANK_BRANCH_A02")
    sib["tactical_tags"] = {"objective_room_location": "roof",
                            "attacker_entrance_count": "3"}
    sib["visual_tags"] = {"architectural_theme": "glass_modern",
                          "wear_state": "new"}
    assert R.main(["add-config", _write(tmp_path, sib), "--dir", reg]) == 1
    # two tactical differences -> accepted
    sib["tactical_tags"] = {"objective_room_location": "roof",
                            "attacker_entrance_count": "2"}
    assert R.main(["add-config", _write(tmp_path, sib), "--dir", reg]) == 0


def test_approved_needs_gates_and_proof(reg, tmp_path):
    rec = _cfg(status="approved", visual_quality_score=4)
    assert R.main(["add-config", _write(tmp_path, rec), "--dir", reg]) == 1
    errs = "\n".join(R.check_all(reg))
    # registry stayed clean (refused record was never written)
    assert errs == ""


def test_approved_full_proof_passes(reg, tmp_path):
    root = tmp_path / "proof"
    root.mkdir()
    paths = {}
    for f in R.CONFIG_PROOF_PATHS:
        rel = f"{f}.file"
        (root / rel).write_text("x")
        paths[f] = rel
    rec = _cfg(status="approved", visual_quality_score=4,
               structural_validation="pass", navigation_validation="pass",
               coordinate_validation="pass", runtime_walktest="pass",
               approval_owner="lead", approval_date="2026-07-17", **paths)
    assert R.main(["add-config", _write(tmp_path, rec), "--dir", reg,
                   "--root", str(root)]) == 0


def test_approved_with_blocking_issue_refused(reg, tmp_path):
    root = tmp_path / "proof"
    root.mkdir()
    paths = {}
    for f in R.CONFIG_PROOF_PATHS:
        rel = f"{f}.file"
        (root / rel).write_text("x")
        paths[f] = rel
    rec = _cfg(status="approved", visual_quality_score=5,
               structural_validation="pass", navigation_validation="pass",
               coordinate_validation="pass", runtime_walktest="pass",
               approval_owner="lead", approval_date="2026-07-17",
               open_issues=[{"severity": "blocking", "title": "hole in floor"}],
               **paths)
    assert R.main(["add-config", _write(tmp_path, rec), "--dir", reg,
                   "--root", str(root)]) == 1


def test_medium_issue_affecting_navigation_refused(reg, tmp_path):
    root = tmp_path / "proof"
    root.mkdir()
    paths = {}
    for f in R.CONFIG_PROOF_PATHS:
        rel = f"{f}.file"
        (root / rel).write_text("x")
        paths[f] = rel
    rec = _cfg(status="approved", visual_quality_score=4,
               structural_validation="pass", navigation_validation="pass",
               coordinate_validation="pass", runtime_walktest="pass",
               approval_owner="lead", approval_date="2026-07-17",
               open_issues=[{"severity": "medium", "affects": "navigation",
                             "title": "narrow catwalk"}],
               **paths)
    assert R.main(["add-config", _write(tmp_path, rec), "--dir", reg,
                   "--root", str(root)]) == 1


def test_mission_orphan_reference_refused(reg, tmp_path):
    m = _msn(cids=("BLD_GHOST_Z99",))
    assert R.main(["add-mission", _write(tmp_path, m), "--dir", reg]) == 1


def test_mission_duplicate_combo_refused(reg, tmp_path):
    R.main(["add-config", _write(tmp_path, _cfg()), "--dir", reg])
    c2 = _cfg(cid="BLD_BANK_BRANCH_A02")
    c2["tactical_tags"] = {"objective_room_location": "roof",
                           "rooftop_access": "yes"}
    c2["visual_tags"] = {"architectural_theme": "glass_modern",
                         "wear_state": "new"}
    R.main(["add-config", _write(tmp_path, c2), "--dir", reg])
    combo = ("BLD_BANK_BRANCH_A01", "BLD_BANK_BRANCH_A02")
    m1 = _msn("MSN_BANK_JOB_01", combo,
              missions=None)
    assert R.main(["add-mission", _write(tmp_path, m1), "--dir", reg]) == 0
    m2 = _msn("MSN_SECOND_HIT_02", combo)
    assert R.main(["add-mission", _write(tmp_path, m2), "--dir", reg]) == 1


def test_hero_needs_two_reviewers(reg, tmp_path):
    R.main(["add-config", _write(tmp_path, _cfg()), "--dir", reg])
    c2 = _cfg(cid="BLD_BANK_BRANCH_A02")
    c2["tactical_tags"] = {"objective_room_location": "roof",
                           "rooftop_access": "yes"}
    c2["visual_tags"] = {"architectural_theme": "glass_modern",
                         "wear_state": "new"}
    R.main(["add-config", _write(tmp_path, c2), "--dir", reg])
    root = tmp_path
    (root / "sites").mkdir()
    (root / "sites" / "bank_job.json").write_text("{}")
    m = _msn("MSN_VAULT_COMPLEX_01",
             ("BLD_BANK_BRANCH_A01", "BLD_BANK_BRANCH_A02"),
             classification="hero", status="approved",
             site_validation="pass", connectivity_validation="pass",
             tactical_validation="pass", godot_import="pass",
             multiplayer_smoke_test="pass",
             approval_owner="lead", approval_date="2026-07-17",
             hero_visual_scores=[5])
    assert R.main(["add-mission", _write(tmp_path, m), "--dir", reg,
                   "--root", str(root)]) == 1


def test_family_overuse_flagged(reg, tmp_path):
    R.main(["add-config", _write(tmp_path, _cfg()), "--dir", reg])
    b, mreg = R.load_registries(reg)
    b["records"][0]["missions"] = [f"MSN_M_{i:02d}" for i in range(5)]
    mreg["records"] = [
        _msn(f"MSN_M_{i:02d}", ("BLD_BANK_BRANCH_A01",),
             name=f"m{i}") for i in range(5)]
    errs = []
    R.validate_cross(b, mreg, errs)
    assert any("appears in 5 missions" in e for e in errs)


def test_portfolio_check_reports_targets(reg):
    errs = R.check_all(reg, portfolio=True)
    joined = "\n".join(errs)
    assert "target exactly 36" in joined
    assert "target exactly 100" in joined
    assert "target exactly 20" in joined


def test_deterministic_output(reg, tmp_path):
    R.main(["add-config", _write(tmp_path, _cfg()), "--dir", reg])
    p = os.path.join(reg, R.BUILDINGS_FILE)
    a = open(p, "rb").read()
    R.main(["add-config", _write(tmp_path, _cfg()), "--dir", reg])
    b = open(p, "rb").read()
    assert a == b
