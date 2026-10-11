# tools/negatives/p15c_c6.sh — P15-CLOSE C6 negatives (permission-prompt keyboard tasks).
# The prompt-focus law lives in its own file and checker; these prove it bites.

_p15c_kp_scratch() {
  local d
  d="$(mktemp -d "$NEG_TMP/p15c-kp.XXXXXX")"
  cp docs/qa/keyboard-tasks-permissions.yaml "$d/tasks.yaml"
  printf '%s' "$d/tasks.yaml"
}

case_p15c_kp_misordered() {
  local f
  f="$(_p15c_kp_scratch)"
  # camera (sensitive) with Deny first: focus would land on Deny.
  "$PY" - "$f" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
i = s.index("capability: camera")
head, tail = s[:i], s[i:]
tail = tail.replace("buttons: [once, session, 7d, deny]", "buttons: [deny, once, session, 7d]", 1)
tail = tail.replace("focus_first: once", "focus_first: deny", 1)
open(p, "w", encoding="utf-8").write(head + tail)
PYEOF
  neg_expect_reject "C6: a sensitive prompt with Deny first reddens (one-time first, plan line 808)" \
    "sensitive capability camera: first button 'deny' != 'once'" \
    "$PY" tools/keyboard_tasks_permissions_check.py --repo . --xr-core ../xr-core --tasks "$f"
}

case_p15c_kp_missing_first() {
  local f
  f="$(_p15c_kp_scratch)"
  "$PY" - "$f" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
s = s.replace("    focus_first: once\n", "", 1)
open(p, "w", encoding="utf-8").write(s)
PYEOF
  neg_expect_reject "C6: a prompt task with no focus_first reddens (where focus lands is data)" \
    'kp-01: missing focus_first' \
    "$PY" tools/keyboard_tasks_permissions_check.py --repo . --xr-core ../xr-core --tasks "$f"
}

case_p15c_kp_missing_task() {
  local f
  f="$(_p15c_kp_scratch)"
  "$PY" - "$f" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
i = s.index("  - id: kp-04")
open(p, "w", encoding="utf-8").write(s[:i])
PYEOF
  neg_expect_reject "C6: dropping a capability's task reddens (one task per core capability)" \
    'capability notifications: 0 task' \
    "$PY" tools/keyboard_tasks_permissions_check.py --repo . --xr-core ../xr-core --tasks "$f"
}
neg_register p15c_kp_misordered
neg_register p15c_kp_missing_first
neg_register p15c_kp_missing_task
