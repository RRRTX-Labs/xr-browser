"""build/workflow_grants.py — the required-grants table (P11-T0-c).

Every rule below is EMPIRICAL: it was proven by a real run, real job logs, or
the platform's own documentation — never by hypothesis. Each rule carries its
proof. Called from build/workflow_lint.py (same findings stream, same exit
codes), importable for tests.

THE REFUTED HYPOTHESIS (recorded so nobody re-adds it):
  The phase brief asserted compat-beta-parity's scheduled failure
  (run 34574063042) was caused by `actions/upload-artifact` lacking an
  `actions: write` token scope, and asked for a lint rule encoding that.
  The job log of the failing step (job 103182443929, step "Upload the
  compat-parity evidence") says otherwise:

      ##[error]Invalid pattern '../xr-core/test/corpus/'.
      Relative pathing '.' and '..' is not allowed.

  and the nightly-rebase-build lane (run 34571026698, SAME head ef3477925,
  SAME action version, SAME `permissions: contents: read`) uploaded its
  artifacts successfully. upload-artifact needs no special scope; granting
  `actions: write` everywhere would have been exactly the over-grant this
  table exists to prevent — and the real failure would still be red. Hence:
  Rule A (the path law, the true root cause) is in the table, and there is
  deliberately NO "upload-artifact => actions: write" rule.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------- rule table

# A. PATH LAW (the proven compat-beta-parity killer, run 34574063042):
#    artifact `with.path` must be workspace-relative — no '..', no leading
#    '/'. No token grant can fix this; it fails before auth is consulted.
# B. `git push` / `git tag` in a run block      => contents: write.
# C. `gh pr <write-verb>`                       => pull-requests: write.
# D. `gh issue <write-verb>`                     => issues: write.
# E. `gh release <write-verb>`                   => contents: write.
# F. security-events: write WITHOUT a codeql/upload-sarif step => over-grant.
# G. actions/cache + contents: write (with no B/E pattern)     => over-grant
#    (the cache action talks to the Actions cache service with its own
#    scoped token; contents: write buys it nothing).
# H. upload-pages-artifact => pages: write; deploy-pages => pages: write +
#    id-token: write (documented Pages OIDC flow).

_ARTIFACT_ACTIONS = ("actions/upload-artifact@", "actions/download-artifact@")
_PUSH_RE = re.compile(r"\bgit\s+(?:push|tag)\b")
_GH_PR_RE = re.compile(
    r"\bgh\s+pr\s+(?:comment|create|edit|review|merge|ready|close)\b")
_GH_ISSUE_RE = re.compile(
    r"\bgh\s+issue\s+(?:comment|create|close|reopen|edit)\b")
_GH_RELEASE_RE = re.compile(
    r"\bgh\s+release\s+(?:upload|create|delete|edit)\b")


def _pushes(run_text: str) -> bool:
    """True when a non-dry-run `git push`/`git tag` appears (line-wise, so a
    dry-run elsewhere in the block cannot mask a real push)."""
    return any(_PUSH_RE.search(ln) and "--dry-run" not in ln
               for ln in run_text.splitlines())


def _strip_comments(run_text: str) -> str:
    out = []
    for line in run_text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def effective_permissions(doc: dict, job: dict) -> Any:
    """Job-level permissions override workflow-level (GitHub semantics)."""
    perms = job.get("permissions", doc.get("permissions"))
    return perms if perms is not None else {}


def _granted(perms: Any, scope: str, want: str = "write") -> bool:
    if isinstance(perms, str):
        return perms in ("write-all",) if want == "write" else True
    if not isinstance(perms, dict):
        return False
    return perms.get(scope) == want


def check_grants(text: str, rel: str) -> list[str]:
    """Findings for one workflow file's text. [] if it will not parse
    (syntax is the expression checker's beat, not ours)."""
    try:
        import yaml  # noqa: PLC0415 — pinned dev dep, lazy for text tools
        doc = yaml.safe_load(text)
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        return []
    findings: list[str] = []
    for job_name, job in doc["jobs"].items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps") or []
        uses = [str(s.get("uses", "")) for s in steps if isinstance(s, dict)]
        run_text = _strip_comments("\n".join(
            str(s.get("run", "")) for s in steps if isinstance(s, dict)))
        perms = effective_permissions(doc, job)
        where = f"{rel} job '{job_name}'"

        # A. artifact path law (run 34574063042 root cause)
        for s in steps:
            if not isinstance(s, dict):
                continue
            u = str(s.get("uses", ""))
            if not any(u.startswith(a) for a in _ARTIFACT_ACTIONS):
                continue
            w = s.get("with") or {}
            p = str(w.get("path", ""))
            bad = [ln.strip() for ln in p.splitlines()
                   if ln.strip() and (".." in ln or ln.strip().startswith("/"))]
            if bad:
                findings.append(
                    f"{where}: artifact path {bad} violates the path law — "
                    "upload/download-artifact reject '..' and absolute "
                    "paths BEFORE any token is consulted (proof: scheduled "
                    "run 34574063042, job 103182443929: \"Invalid pattern "
                    "'../xr-core/test/corpus/'. Relative pathing '.' and "
                    "'..' is not allowed.\"). Stage the files inside the "
                    "workspace instead. NOTE: this is NOT a permissions "
                    "problem — nightly run 34571026698 uploaded fine with "
                    "identical grants; no `actions: write` rule exists "
                    "because the hypothesis was disproven by those logs.")

        # B. git push/tag => contents: write
        if _pushes(run_text) and not _granted(perms, "contents"):
            have = perms.get("contents", "<none>") if isinstance(perms, dict) \
                else perms
            findings.append(
                f"{where}: run block does `git push`/`git tag` but "
                f"permissions grant contents={have} — the push will be "
                "refused by the token; required grant: contents: write "
                "(rule B).")

        # C/D/E. gh write verbs
        if _GH_PR_RE.search(run_text) and not _granted(perms,
                                                       "pull-requests"):
            findings.append(
                f"{where}: `gh pr` write verb without pull-requests: write "
                "(rule C) — the API call will 403.")
        if _GH_ISSUE_RE.search(run_text) and not _granted(perms, "issues"):
            findings.append(
                f"{where}: `gh issue` write verb without issues: write "
                "(rule D) — the API call will 403.")
        if _GH_RELEASE_RE.search(run_text) and not _granted(perms, "contents"):
            findings.append(
                f"{where}: `gh release` write verb without contents: write "
                "(rule E) — release assets are repo contents.")

        # F. over-grant: security-events: write with nothing that consumes it
        if (_granted(perms, "security-events")
                and not any("github/codeql-action" in u or "upload-sarif" in u
                            for u in uses)):
            findings.append(
                f"{where}: over-grant — security-events: write declared but "
                "no codeql/upload-sarif step consumes it (rule F). Least "
                "privilege: drop the grant or wire the step.")

        # G. over-grant: cache + contents: write without a push pattern
        if (any(u.startswith("actions/cache@") for u in uses)
                and _granted(perms, "contents")
                and not _pushes(run_text)
                and not _GH_RELEASE_RE.search(run_text)):
            findings.append(
                f"{where}: over-grant — actions/cache never needs "
                "contents: write (rule G; the cache service uses its own "
                "scoped token).")

        # H. pages flow
        if any("actions/upload-pages-artifact@" in u for u in uses) \
                and not _granted(perms, "pages"):
            findings.append(
                f"{where}: upload-pages-artifact without pages: write "
                "(rule H, documented Pages flow).")
        if any("actions/deploy-pages@" in u for u in uses) and not (
                _granted(perms, "pages") and _granted(perms, "id-token")):
            findings.append(
                f"{where}: deploy-pages without pages: write + id-token: "
                "write (rule H — the deployment is OIDC-authenticated).")

    return findings
