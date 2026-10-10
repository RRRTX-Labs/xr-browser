# tools/negatives/p14c_c1.sh — P14-CLOSE C-1: the identity-chrome state law
# and its structural snapshots must REDDEN on planted defects.
#
# Each plant is applied to an in-memory copy of the REAL states.json /
# tokens.json / grdp / templates.cc (read from the pinned sibling) and run
# through tools/identity_chrome_check.py's own law, or, for snapshots, to a
# per-case scratch copy of the committed snapshot directory (mktemp -d under
# NEG_TMP). Nothing is written into either repo. The TS-core drift negative
# is the lane's own --plant-drift (tools/checks/p14_gates.sh).
# Sourced by tools/run_negatives.sh.

_p14c_c1_run() {   # <plant> -> runs the law on a planted copy; exit 1 + FAIL lines if it bites
  env PLANT="$1" CORE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/../xr-core" \
    SCRATCH="$2" "$PY" - <<'PYEOF'
import copy, json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, "tools")
import identity_chrome_check as m
core, plant = Path(os.environ["CORE"]), os.environ["PLANT"]
table = json.loads((core / m.CHROME / "states.json").read_text(encoding="utf-8"))
themes = json.loads((core / "ui/themes/tokens.json").read_text(encoding="utf-8"))["themes"]
ids = m.grdp_ids((core / "l10n/xr_strings.grdp").read_text(encoding="utf-8"))
tmpl = m.templates((core / "identity/core/templates.cc").read_text(encoding="utf-8"))
if plant == "no-sr":
    table["states"]["planted"] = {"class": "xr-idc--planted", "accessible_name": "idchrome.pill",
                                  "route": "idchrome.route.direct", "window_border": None}
    table["samples"].append(dict(table["samples"][0], state="planted"))
elif plant == "missing-msg":
    ids.discard(table["states"]["disposable"]["sr"])
elif plant == "template-drift":
    table["samples"][0]["color"] = "#123456"
elif plant == "pill-contrast":
    themes["dark"]["text"] = themes["dark"]["surface-raised"]
elif plant == "no-sample":
    table["samples"] = [s for s in table["samples"] if s["state"] != "tor-unbound"]
if plant.startswith("snapshot-"):
    want = m.snapshots(table, themes)
    d = Path(os.environ["SCRATCH"]) / "snapshots"
    shutil.copytree(core / m.CHROME / "snapshots", d)
    first = sorted(want)[0]
    if plant == "snapshot-edit":
        (d / first).write_text((d / first).read_text().replace('"px": 2', '"px": 3', 1))
    elif plant == "snapshot-missing":
        (d / first).unlink()
    else:
        (d / "rail.sepia.json").write_text("{}\n")
    fails = m.check_snapshots(d, want)
else:
    fails = m.laws(table, themes, ids, tmpl)
for f in fails:
    print(f"law-fail: {plant}: {f}")
sys.exit(1 if fails else 0)
PYEOF
}

neg_register p14c_c1_identity_chrome_law_reddens_on_each_plant
case_p14c_c1_identity_chrome_law_reddens_on_each_plant() {
  local plant pat W
  for plant in no-sr missing-msg template-drift pill-contrast no-sample \
               snapshot-edit snapshot-missing snapshot-stale; do
    case "$plant" in
      no-sr) pat="state planted: no sr" ;;
      missing-msg) pat="sr message 'idchrome.sr.disposable' is not in xr_strings.grdp" ;;
      template-drift) pat="drifted from templates.cc" ;;
      pill-contrast) pat="pill text contrast" ;;
      no-sample) pat="state tor-unbound: no sample renders it" ;;
      snapshot-edit|snapshot-missing) pat="differs from the generator" ;;
      snapshot-stale) pat="rail.sepia.json has no layout x theme" ;;
    esac
    W="$(mktemp -d "${NEG_TMP:-${TMPDIR:-/tmp}}/p14c-c1.XXXXXX")"
    neg_expect_reject "identity chrome: planted $plant reddens the law" "$pat" _p14c_c1_run "$plant" "$W"
    rm -rf "$W"
  done
}
