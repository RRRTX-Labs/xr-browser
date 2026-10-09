# P15 planted-defect check against the OWNING suite (the mutation map's disposition).
#
# Runs the eleven planted defects (M01-M11, texts read from mutate.py, single source),
# plus M02c (the compile-clean deny-list variant), each on a scratch copy of xr-core.
# Owner: policy/core defects -> policy/tests; permissions/core defects -> permissions/tests.
# For M01-M05 and M02c the permissions cross-core suite is also run (secondary).
# Verdict: KILLED when make exits non-zero. Kind: test (a reported check or FAILED line),
# crash (SIGSEGV/abort), compile (the build failed: NOT a test kill), other.
# Control: the unmutated tree is run first; it must pass for both suites.
import ast, os, pathlib, re, shutil, subprocess, sys

SRC = pathlib.Path("/home/user/xr-core")
ROOT = pathlib.Path("/var/tmp/p15/planted")
HERE = pathlib.Path(__file__).resolve().parent
EXPECT_HEAD = "4d6672d"

head = subprocess.run(["git", "-C", str(SRC), "rev-parse", "--short", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
if head != EXPECT_HEAD:
    sys.exit(f"xr-core is at {head}, expected {EXPECT_HEAD}")

def mutants_from(path, var):
    tree = ast.parse((HERE / path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == var:
            return ast.literal_eval(node.value)
    sys.exit(f"{var} not found in {path}")

ALL = mutants_from("mutate.py", "MUTANTS")
assert [m[0][:3] for m in ALL] == [f"M{i:02d}" for i in range(1, 12)], "expected M01..M11"
owner = {m[0][:3]: ("policy" if m[4] == "policy" else "perm") for m in ALL}
rows = [("CONTROL unmutated", None, None, None, None)] + list(ALL)
for name, rel, old, new, suite in ALL:
    if name.startswith("M02"):
        c = name.replace("M02", "M02c", 1).replace("deny-list ignored", "deny-list ignored (compile-clean)", 1)
        rows.append((c, rel, old, new.replace("if (false) {", "if (id == req.identity && false) {", 1), suite))

def classify(out, rc):
    if re.search(r"Segmentation fault|Aborted|Error 13[49]", out):
        return "crash"
    if "error:" in out:
        return "compile"
    if re.search(r"FAILED|TESTS FAILED|checks, [1-9][0-9]* failures", out):
        return "test"
    return "other" if rc != 0 else "-"

def run_suite(tree, target):
    env = dict(os.environ, XR_BROWSER_ROOT="/home/user/xr-browser")
    p = subprocess.run(["make", "-C", str(tree / "xr-core" / target), "test"],
                       capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    evidence = [l.strip() for l in out.splitlines()
                if re.search(r"FAILED|checks, [1-9][0-9]* failures|error:|Segmentation fault", l)][:1]
    return p.returncode, classify(out, p.returncode), (evidence[0][:150] if evidence else "")

print(f"# xr-core head {head}; scratch copies under {ROOT}; TMPDIR-independent", flush=True)
for name, rel, old, new, suite in rows:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    (ROOT / "xr-core").mkdir(parents=True)
    for d in ("policy", "common", "permissions"):
        shutil.copytree(SRC / d, ROOT / "xr-core" / d, ignore=shutil.ignore_patterns("build", "*.o"))
    if rel is not None:
        f = ROOT / "xr-core" / rel
        s = f.read_text(encoding="utf-8")
        if s.count(old) != 1:
            print(f"{name} | ANCHOR-MISSING ({s.count(old)})", flush=True)
            continue
        f.write_text(s.replace(old, new), encoding="utf-8")
    if name.startswith("CONTROL"):
        for tgt, lbl in (("policy/tests", "policy"), ("permissions/tests", "perm")):
            rc, kind, ev = run_suite(ROOT, tgt)
            print(f"{name} | owner={lbl} | rc={rc} | {'PASS' if rc == 0 else 'FAIL'} | {ev}", flush=True)
        continue
    key = name[:3] if not name.startswith("M02c") else "M02c"
    tgt = "policy/tests" if owner.get(name[:3], "policy") == "policy" else "permissions/tests"
    rc, kind, ev = run_suite(ROOT, tgt)
    verdict = "KILLED" if rc != 0 else "SURVIVED"
    line = f"{name} | owner={tgt.split('/')[0]} | {verdict} rc={rc} | kind={kind} | {ev}"
    if key in ("M01", "M02c", "M03", "M04", "M05"):
        rc2, kind2, ev2 = run_suite(ROOT, "permissions/tests")
        line += f" || cross-core: {'KILLED' if rc2 else 'SURVIVED'} rc={rc2} kind={kind2} | {ev2}"
    print(line, flush=True)
shutil.rmtree(ROOT, ignore_errors=True)
print("DONE", flush=True)
