import subprocess, shutil, pathlib, sys, os
SRC = pathlib.Path("/home/user/xr-core")
WORK = pathlib.Path("/tmp/p15/mut")
MUTANTS_ALL = [
 ("M01 7d fail-open at equality", "policy/core/resolve.cc", "return g.expires_at > req.now_ms;", "return g.expires_at >= req.now_ms;", "policy"),
 ("M02 deny-list ignored", "policy/core/resolve.cc", "    if (id == req.identity) {\n      DenyAllPermissions(p);", "    if (false) {\n      DenyAllPermissions(p);", "policy"),
 ("M03 corrupt overlay not denying", "policy/core/resolve.cc", "  if (ov.corrupt) {\n    DenyAllPermissions(p);", "  if (false) {\n    DenyAllPermissions(p);", "policy"),
 ("M04 grant ignores identity (cross-identity leak)", "policy/core/resolve.cc", "if (g.identity != req.identity || g.domain != req.registrable_domain) continue;", "if (g.domain != req.registrable_domain) continue;", "policy"),
 ("M05 malformed overlay treated as absent (fail-open)", "policy/core/resolve_io.cc", "      req.permission_overlay.present = true;\n      req.permission_overlay.corrupt = true;", "      req.permission_overlay.present = false;", "policy"),
 ("M06 store round-trip check removed (dup keys accepted)", "permissions/core/store.cc", "if (pr.value.Canonical() != text) return bad;", "(void)0;", "perm"),
 ("M07 sweep boundary fail-open (< instead of <=)", "permissions/core/ops.cc", "g.expires_at <= now_ms) {  // fail-closed at ==", "g.expires_at < now_ms) {  // fail-closed at ==", "perm"),
 ("M08 fallback mislabelled as identity overlay", "permissions/core/merge.cc", "{global_state, SiteSource::kGlobalFallback, \"perm.source.global_fallback\"}", "{global_state, SiteSource::kIdentityOverlay, \"perm.source.identity\"}", "perm"),
 ("M09 ceiling overflow not logged", "permissions/core/present.cc", "  if (prompts_in_last_hour >= kT3PromptsPerHour) {\n    d.verdict = PromptVerdict::kDemoteT2;\n    d.logged = true;", "  if (prompts_in_last_hour >= kT3PromptsPerHour) {\n    d.verdict = PromptVerdict::kDemoteT2;\n    d.logged = false;", "perm"),
 ("M10 extras accept kAllow", "permissions/core/envelope.cc", "  return false;  // kAllow is refused here, by construction", "  if (s == \"kAllow\") { *out = CapState::kAllow; return true; }\n  return false;", "perm"),
 ("M11 origin redaction disabled", "permissions/core/audit.cc", "bool RedactOrigin(std::string_view input, std::string* out) {\n", "bool RedactOrigin(std::string_view input, std::string* out) {\n  if (!input.empty()) { *out = std::string(input); return true; }\n", "perm"),
]
MUTANTS = [m[:4] + ("perm",) for m in MUTANTS_ALL if m[0][:3] in ("M01","M02","M03","M04","M05")]
results = []
for name, rel, old, new, suite in MUTANTS:
    if WORK.exists(): shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    for d in ("policy", "common", "permissions"):
        shutil.copytree(SRC / d, WORK / "xr-core" / d, ignore=shutil.ignore_patterns("build", "*.o"))
    f = WORK / "xr-core" / rel
    s = f.read_text(encoding="utf-8")
    if s.count(old) != 1:
        results.append((name, "ANCHOR-MISSING", s.count(old))); continue
    f.write_text(s.replace(old, new), encoding="utf-8")
    env = dict(os.environ, XR_BROWSER_ROOT="/home/user/xr-browser")
    target = "policy/tests" if suite == "policy" else "permissions/tests"
    p = subprocess.run(["make", "-C", str(WORK / "xr-core" / target), "test"], capture_output=True, text=True, env=env)
    tail = [l for l in (p.stdout + p.stderr).splitlines() if "FAILED" in l or "failures" in l and "0 failures" not in l][:2]
    killed = p.returncode != 0
    results.append((name, "KILLED" if killed else "SURVIVED", (tail[0][:120] if tail else "")))
    print(results[-1], flush=True)
print("\nSUMMARY:", sum(1 for r in results if r[1] == "KILLED"), "killed of", len(results))
