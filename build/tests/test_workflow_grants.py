"""build/tests/test_workflow_grants.py — the required-grants table (P11-T0-c).

Every rule is empirical; the marquee test is the DISPROOF one: a clean
workspace-relative upload-artifact under `contents: read` must produce ZERO
findings, because the phase brief's `actions: write` hypothesis was refuted
by the job logs (run 34574063042 / job 103182443929: "Invalid pattern
'../xr-core/test/corpus/'. Relative pathing '.' and '..' is not allowed.")
and by the nightly lane (run 34571026698) uploading fine with identical
grants. Encoding the disproven rule would force an over-grant everywhere.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
REPO = BUILD.parent
sys.path.insert(0, str(BUILD))

import workflow_grants  # noqa: E402

UPLOAD_PIN = "actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4"
CHECKOUT_PIN = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"


def wf(steps: str, perms: str = "    permissions:\n      contents: read\n",
       top: str = "") -> str:
    return (f"name: t\non: push\n{top}jobs:\n  j:\n    runs-on: ubuntu-latest\n"
            f"{perms}    timeout-minutes: 5\n    steps:\n{steps}")


def test_artifact_dotdot_path_is_the_proven_killer():
    text = wf(f"      - uses: {UPLOAD_PIN} # v5.0.0\n"
              "        with:\n          name: ev\n"
              "          path: |\n            ../xr-core/test/corpus/\n")
    hits = workflow_grants.check_grants(text, "t.yml")
    assert len(hits) == 1 and "path law" in hits[0]
    assert "34574063042" in hits[0]  # the finding carries its proof


def test_artifact_absolute_path_flagged():
    text = wf(f"      - uses: {UPLOAD_PIN} # v5.0.0\n"
              "        with:\n          name: ev\n          path: /tmp/ev\n")
    assert any("path law" in h
               for h in workflow_grants.check_grants(text, "t.yml"))


def test_disproof_clean_upload_under_contents_read_is_zero_findings():
    # THE rule that must NOT exist: upload-artifact => actions: write.
    text = wf(f"      - uses: {CHECKOUT_PIN} # v4.4.0\n"
              f"      - uses: {UPLOAD_PIN} # v5.0.0\n"
              "        with:\n          name: ev\n"
              "          path: |\n            compat-parity-evidence/\n")
    assert workflow_grants.check_grants(text, "t.yml") == []
    # and the module records WHY (so nobody re-adds the hypothesis)
    assert "disproven" in workflow_grants.__doc__.lower() or \
           "REFUTED" in workflow_grants.__doc__


def test_git_push_requires_contents_write():
    text = wf("      - run: |\n          git push origin HEAD:refs/heads/x\n")
    hits = workflow_grants.check_grants(text, "t.yml")
    assert any("rule B" in h for h in hits)
    # with the grant: clean
    text_ok = wf("      - run: |\n          git push origin HEAD:refs/heads/x\n",
                 perms="    permissions:\n      contents: write\n")
    assert workflow_grants.check_grants(text_ok, "t.yml") == []
    # dry-run is not a push
    text_dry = wf("      - run: git push --dry-run origin main\n")
    assert workflow_grants.check_grants(text_dry, "t.yml") == []


def test_gh_write_verbs_require_their_scopes():
    pr = wf("      - run: gh pr comment 12 --body hi\n")
    assert any("rule C" in h for h in workflow_grants.check_grants(pr, "t"))
    iss = wf("      - run: gh issue close 12\n")
    assert any("rule D" in h for h in workflow_grants.check_grants(iss, "t"))
    rel = wf("      - run: gh release upload v1 file.zip\n")
    assert any("rule E" in h for h in workflow_grants.check_grants(rel, "t"))


def test_security_events_write_without_codeql_is_an_overgrant():
    text = wf("      - run: echo hi\n",
              perms="    permissions:\n      contents: read\n"
                    "      security-events: write\n")
    assert any("rule F" in h for h in workflow_grants.check_grants(text, "t"))
    # consumed by codeql: legitimate
    text_ok = wf("      - uses: github/codeql-action/analyze@v3\n",
                 perms="    permissions:\n      contents: read\n"
                       "      security-events: write\n")
    # (the unpinned v3 will redden check_supply_chain, not this table)
    assert not any("rule F" in h
                   for h in workflow_grants.check_grants(text_ok, "t"))


def test_cache_with_contents_write_is_an_overgrant():
    text = wf("      - uses: actions/cache@v4\n      - run: echo hi\n",
              perms="    permissions:\n      contents: write\n")
    assert any("rule G" in h for h in workflow_grants.check_grants(text, "t"))
    # cache + write + a real push elsewhere in the job: legitimate
    text_ok = wf("      - uses: actions/cache@v4\n"
                 "      - run: |\n          git push origin main\n",
                 perms="    permissions:\n      contents: write\n")
    assert not any("rule G" in h
                   for h in workflow_grants.check_grants(text_ok, "t"))


def test_pages_flow_rules():
    up = wf("      - uses: actions/upload-pages-artifact@v3\n")
    assert any("rule H" in h for h in workflow_grants.check_grants(up, "t"))
    dep = wf("      - uses: actions/deploy-pages@v4\n",
             perms="    permissions:\n      pages: write\n")
    hits = workflow_grants.check_grants(dep, "t")
    assert any("id-token" in h for h in hits)


def test_job_permissions_override_workflow_permissions():
    # top-level read, job-level write: the push is legitimate
    text = ("name: t\non: push\npermissions:\n  contents: read\njobs:\n"
            "  j:\n    runs-on: ubuntu-latest\n"
            "    permissions:\n      contents: write\n"
            "    timeout-minutes: 5\n    steps:\n"
            "      - run: |\n          git push origin main\n")
    assert workflow_grants.check_grants(text, "t.yml") == []


def test_shipped_workflows_are_clean_under_the_table():
    for f in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        hits = workflow_grants.check_grants(f.read_text(encoding="utf-8"),
                                            f.name)
        assert hits == [], f"{f.name}: {hits}"
