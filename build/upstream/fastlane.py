"""build/upstream/fastlane.py — the security fast-lane (P3-T5, Plan §12.4).

Watch → plan → cherry-pick → rebase-apply → compat smoke → sign (P2
sign_artifact, TEST keys) → report. SLA: 72 h critical/in-the-wild and
14 d high, **measured from TAG PUBLICATION, not announcement**
(docs/contracts/sla-metrics-v1.md). A missed window writes the
feature-freeze marker (§15-R1 kill-switch) — advisory in CI now, hard in
P9's dashboard (stated in every output).

Watch sources (research log R3/R4):
  - ChromiumdashSecurityWatch: chromiumdash fetch_releases (Stable+Extended)
    + gitiles exact-tag verification — both allowlisted; publication time =
    the release row's `time` (epoch ms; cross-checked against versionhistory
    to the millisecond in research). This replaces the phase brief's assumed
    in-tree chrome/desktop/SECURITY_NOTES.md, which does not exist at any rev
    (draft-issue-0001) — the class keeps the name honest.
  - FixtureWatchSource: deterministic drill source (invented CVEs + dates).

Detection honesty (R4): security fixes are NOT distinguishable from ordinary
commits by message markers (0/100 sampled main commits carry CVE refs;
severity lives in the tracker). Detection is therefore release-driven —
every new Stable/Extended release is a candidate until proven otherwise —
and commit-message heuristics are advisory enrichment only. Missed-fix =
SLA breach (L6): the design fails toward MORE candidates, never fewer.

Signing: drill artifacts sign through the P2 interface
(build/signing/sign_artifact.py, TEST keys). Release-key parity is P10
(HG); no unsigned path exists even then — there is no hotfix exception
(L6). `--channel stable` unsigned outputs are structurally refused.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

for _p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    if (_p / "_common.py").exists():
        sys.path.insert(0, str(_p))
        break

from _common import ToolError, main_with_guard  # noqa: E402
from fetch import FetchError, GitilesFetchSource  # noqa: E402


def __getattr__(name: str):  # PEP 562 — lazy re-export (avoids __main__ re-import loops)
    if name == "run_drill":
        from fastlane_drills import run_drill
        return run_drill
    raise AttributeError(name)

SLA_CRITICAL_IIT_H = 72
SLA_HIGH_D = 14
FREEZE_MARKER = "feature-freeze.json"

_SECURITY_RE = re.compile(r"(CVE-\d{4}-\d+|security|use.after.free|sandbox escape|"
                          r"memory corruption|type confusion|heap overflow)", re.I)


@dataclass
class SecurityRelease:
    version: str
    channel: str
    milestone: int | None
    published_at: datetime          # TAG PUBLICATION time (SLA clock start)
    previous_version: str | None
    chromium_hash: str | None
    source: str                     # "real" | "fixture"


@dataclass
class CherryPickItem:
    upstream_sha: str
    subject: str
    risk_class: str                 # explicit-marker | security-wording | unknown
    needs_build: bool = True        # no compiled code exists yet; drills sign the plan artifact
    matched: list[str] = field(default_factory=list)


class WatchSource(Protocol):
    def poll(self) -> list[SecurityRelease]: ...


class ChromiumdashSecurityWatch:
    """Live watch: new Stable/Extended releases (release-driven detection)."""

    def __init__(self, source: GitilesFetchSource | None = None,
                 platform: str = "Windows") -> None:
        self.source = source or GitilesFetchSource()
        self.platform = platform

    def poll(self) -> list[SecurityRelease]:
        out: list[SecurityRelease] = []
        for channel in ("Stable", "Extended"):
            try:
                rows = self.source.releases(channel, self.platform, 5)
            except FetchError as exc:
                raise ToolError(f"watch source unreachable ({channel}): {exc}") from exc
            for r in rows:
                ts = r.get("time")
                if not ts:
                    continue
                published = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                out.append(SecurityRelease(
                    version=str(r.get("version")), channel=channel,
                    milestone=r.get("milestone"), published_at=published,
                    previous_version=r.get("previous_version"),
                    chromium_hash=(r.get("hashes") or {}).get("chromium"),
                    source="real"))
        return out


class FixtureWatchSource:
    """Deterministic drill source (invented CVEs + tag dates, SIMULATED)."""

    def __init__(self, releases: list[dict[str, Any]]) -> None:
        self._rows = releases

    def poll(self) -> list[SecurityRelease]:
        out = []
        for r in self._rows:
            out.append(SecurityRelease(
                version=r["version"], channel=r.get("channel", "Stable"),
                milestone=r.get("milestone"),
                published_at=datetime.fromisoformat(r["published_at"]),
                previous_version=r.get("previous_version"),
                chromium_hash=r.get("chromium_hash"), source="fixture"))
        return out


def classify_commits(log: list[dict[str, Any]]) -> list[CherryPickItem]:
    """Advisory enrichment from commit messages (R4: never the primary signal)."""
    items: list[CherryPickItem] = []
    for c in log:
        msg = c.get("message", "")
        subject = msg.splitlines()[0] if msg else ""
        matched = sorted(set(_SECURITY_RE.findall(msg)))
        risk = ("explicit-marker" if any(m.startswith("CVE-") for m in matched)
                else "security-wording" if matched else "unknown")
        items.append(CherryPickItem(upstream_sha=c.get("commit", "?"),
                                    subject=subject, risk_class=risk, matched=matched))
    return items


def build_plan(release: SecurityRelease, source: GitilesFetchSource | None = None
               ) -> dict[str, Any]:
    """cherry-pick-plan.json for one security release: range commits between
    previous_version and version, advisory risk classes, needs_build=true."""
    items: list[CherryPickItem] = []
    if release.source == "real" and source is not None and release.previous_version:
        try:
            src = GitilesFetchSource() if source is None else source
            frm = src.ref_value(f"tags/{release.previous_version}")
            to = src.ref_value(f"tags/{release.version}")
            log = src.log(to, 50, start=frm)
            items = classify_commits(log)
        except FetchError:
            items = []  # tag range unavailable: plan ships with metadata only; never fabricated
    plan = {
        "schema_version": 1,
        "tool": "xr-fastlane",
        "source": release.source,           # SIMULATED for fixtures — validator law
        "release": {
            "version": release.version, "channel": release.channel,
            "milestone": release.milestone,
            "published_at": release.published_at.isoformat(),
            "previous_version": release.previous_version,
            "chromium_hash": release.chromium_hash,
        },
        "sla_hours": {"critical_iit": SLA_CRITICAL_IIT_H, "high_days": SLA_HIGH_D},
        "deadlines": {
            "critical_iit": (release.published_at + timedelta(hours=SLA_CRITICAL_IIT_H)).isoformat(),
            "high": (release.published_at + timedelta(days=SLA_HIGH_D)).isoformat(),
        },
        "candidates": [vars(i) for i in items],
        "detection": "release-driven (every new Stable/Extended release is a candidate; "
                     "commit-message heuristics are advisory — research R4)",
        "needs_build": True,               # no compiled code exists yet (P3); drills sign the PLAN
        "signing": "P2 sign_artifact interface, TEST keys; release-key parity is P10 (HG); "
                   "no unsigned path exists even then (L6)",
    }
    return plan


def sla_clock(*, since_tag: str, published_at: datetime | None = None,
              source: GitilesFetchSource | None = None,
              now: datetime | None = None, severity: str = "critical"
              ) -> dict[str, Any]:
    """./scripts/build sla --since <tag>: deadlines from TAG PUBLICATION.
    Breach ⇒ feature-freeze marker (§15-R1; advisory now, hard in P9 dashboard)."""
    now = now or datetime.now(timezone.utc)
    if published_at is None:
        src = source or GitilesFetchSource()
        rows = src.releases("Stable", "Windows", 30) + src.releases("Extended", "Windows", 30)
        row = next((r for r in rows if r.get("version") == since_tag), None)
        if row is None or not row.get("time"):
            raise ToolError(f"tag {since_tag!r} not found in watch sources "
                            "(publication time is the SLA start — never guessed)")
        published_at = datetime.fromtimestamp(row["time"] / 1000, tz=timezone.utc)
    deadline = (published_at + timedelta(hours=SLA_CRITICAL_IIT_H) if severity == "critical"
                else published_at + timedelta(days=SLA_HIGH_D))
    remaining_h = round((deadline - now).total_seconds() / 3600, 2)
    breached = now > deadline
    return {
        "tool": "xr-sla", "since_tag": since_tag, "severity": severity,
        "tag_published_at": published_at.isoformat(),
        "deadline": deadline.isoformat(),
        "now": now.isoformat(),
        "remaining_hours": remaining_h, "breached": breached,
        "law": "measured from TAG PUBLICATION, not announcement "
               "(docs/contracts/sla-metrics-v1.md)",
        "on_breach": f"feature-freeze marker {FREEZE_MARKER} (§15-R1 kill-switch; "
                     "advisory in CI now, HARD in P9's dashboard — stated)",
        "pre_ga_note": "XR has no stable release until P10; pre-GA breach markers are "
                       "ADVISORY ONLY — the kill-switch arms at the first stable promotion",
    }


def write_freeze_marker(out_dir: Path, reason: str) -> Path:
    marker = {
        "schema_version": 1, "marker": "feature-freeze",
        "law": "Plan §15-R1 / §12.4 kill-switch — a missed SLA window freezes feature work",
        "reason": reason,
        "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "advisory_until": "P9 dashboard consumes this as a HARD gate; today CI treats it as advisory (stated)",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / FREEZE_MARKER
    p.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return p


def sign_plan_via_p2(plan_path: Path, out_dir: Path, repo_root_: Path) -> Path:
    """Sign the drill artifact through the P2 interface ONLY (test keys).
    Refuses release/stable channels structurally — same law as P2."""
    sys.path.insert(0, str(repo_root_ / "build" / "signing"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sign_artifact", repo_root_ / "build" / "signing" / "sign_artifact.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    # P2 interface: --artifact <path> --channel <dev|nightly-test> --os <linux|mac|win>
    r = subprocess.run(
        [sys.executable, str(repo_root_ / "build" / "signing" / "sign_artifact.py"),
         "--artifact", str(plan_path), "--channel", "dev", "--os", "linux"],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise ToolError(f"P2 signing refused (correct behavior for anything but "
                        f"dev/nightly-test): {r.stderr.strip()[-500:]}")
    return plan_path


def validate_plan(plan: dict) -> list[str]:
    fails: list[str] = []
    if plan.get("schema_version") != 1:
        fails.append("schema_version must be 1")
    if plan.get("source") not in ("real", "fixture"):
        fails.append(f"source must be real|fixture (got {plan.get('source')!r})")
    rel = plan.get("release", {})
    for key in ("version", "published_at", "channel"):
        if not rel.get(key):
            fails.append(f"release.{key} required")
    if not plan.get("deadlines", {}).get("critical_iit"):
        fails.append("deadlines.critical_iit required")
    return fails


# ---------------------------------------------------------------------------
# CLI: watch | plan | sla | drill
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="xr-fastlane",
        description="Security fast-lane: watch releases, build cherry-pick plans, "
                    "SLA clock (from tag publication), synthetic drills.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="poll watch sources (live, allowlisted)")
    w.add_argument("--json", action="store_true")
    p = sub.add_parser("plan", help="build a cherry-pick plan for a release")
    p.add_argument("--version", required=True)
    p.add_argument("--out", default="work/upstream-cache")
    s = sub.add_parser("sla", help="SLA clock from TAG PUBLICATION")
    s.add_argument("--since", required=True, help="tag/version string")
    s.add_argument("--severity", choices=["critical", "high"], default="critical")
    s.add_argument("--at", help="ISO now override (drills); default: real now")
    d = sub.add_parser("drill", help="run the synthetic drills (SIMULATED, fixture data)")
    d.add_argument("--out", default="work/upstream-cache/fastlane")
    args = parser.parse_args()

    if args.cmd == "watch":
        watch = ChromiumdashSecurityWatch()
        rels = watch.poll()
        for r in rels:
            print(f"{r.channel:<9} {r.version:<18} published {r.published_at.isoformat()} "
                  f"(M{r.milestone}, prev {r.previous_version})")
        print(f"{len(rels)} release(s) polled; every new Stable/Extended release is a "
              "candidate (detection is release-driven — research R4)")
        return 0

    if args.cmd == "plan":
        watch = ChromiumdashSecurityWatch()
        rels = [r for r in watch.poll() if r.version == args.version]
        if not rels:
            raise ToolError(f"release {args.version!r} not seen in watch sources")
        plan = build_plan(rels[0], source=GitilesFetchSource())
        fails = validate_plan(plan)
        out = Path(args.out) / f"cherry-pick-plan-{args.version}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(f"plan: {out} ({len(plan['candidates'])} candidates, "
              f"deadlines {plan['deadlines']})")
        return 1 if fails else 0

    if args.cmd == "sla":
        now = datetime.fromisoformat(args.at) if args.at else None
        clock = sla_clock(since_tag=args.since, severity=args.severity,
                          now=now, source=GitilesFetchSource())
        print(json.dumps(clock, indent=2))
        if clock["breached"]:
            marker = write_freeze_marker(Path("work/upstream-cache"), (
                f"{args.since} ({args.severity}) deadline {clock['deadline']} missed"))
            print(f"BREACH: feature-freeze marker written: {marker} "
                  "(§15-R1; advisory in CI now, HARD in P9 dashboard — stated)")
        return 0

    if args.cmd == "drill":
        from fastlane_drills import run_drill  # lazy (PEP-562 note above)
        from _common import repo_root
        root = repo_root()
        out = Path(args.out)
        r1 = run_drill(out_dir=out / "drill1-in-window", root=root,
                       label="in-window", published_hours_ago=30.0, expect_breach=False)
        r2 = run_drill(out_dir=out / "drill2-breach", root=root,
                       label="breach", published_hours_ago=80.0, expect_breach=True)
        for r in (r1, r2):
            print(f"drill {r['label']}: {r['verdict']} "
                  f"(apply={r['steps']['apply']} verify={r['steps']['verify']} "
                  f"sign={r['steps']['sign_p2_dev_channel']} "
                  f"unsigned-refused={r['steps']['unsigned_stable_refused']} "
                  f"breach={r['steps']['sla']['breached']} "
                  f"freeze={bool(r['steps']['freeze_marker'])}) "
                  f"[SIMULATED; elapsed {r['elapsed_real_seconds']}s real, "
                  f"{r['simulated_elapsed_hours']}h simulated]")
        ok = r1["verdict"] == "PASS" and r2["verdict"] == "PASS"
        print(f"drills: {'2/2 PASS (SIMULATED)' if ok else 'FAIL'}")
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    main_with_guard(lambda: main())
