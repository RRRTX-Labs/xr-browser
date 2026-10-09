# P15 owning-suite kill check (policy/core overlay mutants vs the POLICY suite).
# Each mutant is applied to a scratch copy of xr-core (policy, common, permissions),
# then `make -C policy/tests test` runs. KILLED = non-zero exit; kind=test means a
# test assertion failed, kind=compile-error means the build failed (not a test kill).
# M02c is the compile-clean deny-list mutant: the original M02 fails -Werror on `id`.
# Mutant texts are read from mutate_policy_overlay.py (single source). Runs from the
# xr-core working tree; the tree must be at the pinned head before the run.
import ast, pathlib, shutil, subprocess, os, sys
SRC = pathlib.Path("/home/user/xr-core")
ROOT = pathlib.Path("/var/tmp/p15/pk")
src = pathlib.Path("/home/user/xr-browser/evidence/P15/mutation/mutate_policy_overlay.py").read_text(encoding="utf-8")
tree = ast.parse(src)
mut_all = None
for node in tree.body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "MUTANTS_ALL":
        mut_all = ast.literal_eval(node.value)
assert mut_all, "MUTANTS_ALL not found"
sel = [m for m in mut_all if m[0][:3] in ("M01", "M02", "M03", "M04", "M05")]
# compile-clean M02: keep `id` used, so -Werror does not reject the build
clean = []
for name, rel, old, new, suite in sel:
    if name.startswith("M02"):
        new2 = new.replace("if (false) {", "if (id == req.identity && false) {", 1)
        assert new2 != new, "M02 rewrite failed"
        clean.append(("M02c deny-list ignored (compile-clean)", rel, old, new2, suite))
    clean.append((name, rel, old, new, suite))
for name, rel, old, new, suite in clean:
    if ROOT.exists(): shutil.rmtree(ROOT)
    (ROOT / "xr-core").mkdir(parents=True)
    for d in ("policy", "common", "permissions"):
        shutil.copytree(SRC / d, ROOT / "xr-core" / d, ignore=shutil.ignore_patterns("build", "*.o"))
    f = ROOT / "xr-core" / rel
    s = f.read_text(encoding="utf-8")
    if s.count(old) != 1:
        print(f"{name}: ANCHOR-MISSING ({s.count(old)})", flush=True); continue
    f.write_text(s.replace(old, new), encoding="utf-8")
    env = dict(os.environ, XR_BROWSER_ROOT="/home/user/xr-browser")
    p = subprocess.run(["make", "-C", str(ROOT / "xr-core" / "policy" / "tests"), "test"],
                       capture_output=True, text=True, env=env)
    out = (p.stdout + p.stderr).splitlines()
    compile_err = [l for l in out if "error:" in l][:1]
    failed = [l for l in out if "FAILED" in l][:2]
    summary = [l for l in out if " checks, " in l and "0 failures" not in l][:2]
    verdict = "KILLED" if p.returncode != 0 else "SURVIVED"
    kind = "compile-error" if compile_err and not failed and not summary else ("test" if (failed or summary) else "other")
    print(f"{name} | {suite} | {verdict} rc={p.returncode} | kind={kind} | {(compile_err or failed or summary or [''])[0][:160]}", flush=True)
shutil.rmtree(ROOT, ignore_errors=True)
print("DONE", flush=True)
