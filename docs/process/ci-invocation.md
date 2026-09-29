# Running the gate the way CI runs it (P13-P0-A)

**The rule, one line: run the gate the way CI runs it.**

`governance.yml` does not run `bash tools/run_checks.sh`. It runs

```yaml
run: |
  if [ -n "$CHECK_RANGE" ]; then
    tools/run_checks.sh "$CHECK_RANGE"
  else
    tools/run_checks.sh
  fi
```

— a **direct exec** of a repo path, with one positional argv element (a git
range, or *no argument at all* when the push range is empty). A direct exec
consults the file's **mode**; `bash <path>` does not. That difference is not a
style preference: on a runner a non-executable file is

```
Process completed with exit code 126
```

which is the failure that kept this repository's `governance` lane red for three
consecutive commits after `5e3d1d4` flipped `tools/run_checks.sh` and
`tools/run_negatives.sh` to `100644`. Every local run was green throughout,
because every local run used `bash`.

## Use it

```bash
tools/run_checks.sh --via-ci-invocation            # no range: full history, exactly as an empty CHECK_RANGE does
tools/run_checks.sh --via-ci-invocation <base>..HEAD
```

The mode does two things, in order:

1. It refuses to run if the entry point is not executable **in the index**
   (what a runner checks out) or on disk, naming exit 126 and the fix
   (`git update-index --chmod=+x <path>`) instead of producing a bare
   `Permission denied`;
2. it then `exec`s the literal workflow command line — same file, same argv,
   same cwd — so the local run and the hosted step are the same process image.

`bash tools/run_checks.sh --via-ci-invocation` (note the `bash`) is the useful
form while the bit is still wrong: the wrapper makes the invisible mode visible
even when the interpreter hides it. That exact shape is a registered negative
(`tools/negatives/p13_p0a.sh`, case `ci_invocation_sees_a_644_entry_point`).

## The laws behind it

* `tools/entrypoint_mode_check.py` — **Law 1**: every `.github/workflows/*.yml`
  `run:` block is parsed, and every command whose first token is a repo path
  executed **directly** must be `100755` in the git index. `bash <path>` /
  `python3 <path>` / `node <path>` invocations are **exempt**, and the tool says
  so in its own output (the interpreter is the executable; the file's mode is
  not load-bearing) — an exemption that is printed is reviewable, one that is
  silent is a hole. **Law 2** (`--range`): no commit in the pushed range may
  change a tracked file's index mode from `100755` to `100644`. Replayed over
  history, Law 2 returns exactly the incident:

  ```
  FAIL (mode drift): 5e3d1d4 (P12-T0-d: moving NEG_TMP into the repo broke four gates…) :
      tools/run_checks.sh lost its executable bit (100755 -> 100644) in this range
  ```

* `tools/inplace.py` — every **in-place rewrite** of an existing file copies the
  pre-write `stat` mode onto its replacement before `os.replace` publishes it
  (`rewrite_in_place`, `rewrite_bytes_in_place`). A new file gets an explicit
  mode, never the umask. `--self-test` proves a `0755` fixture survives a
  rewrite, and `--simulate-naive` proves the *assertion* can fail (the
  write-new-then-replace shape loses the bit — the `5e3d1d4` class, reproduced).

Both laws run in the `governance` gate (`tools/checks/p13_gates.sh`, lane
`p13_p0_gates`), so they are enforced locally, in CI, and at push time.
