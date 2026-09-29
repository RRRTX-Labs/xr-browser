#!/usr/bin/env python3
"""tools/wfrun.py — the `.github/workflows/*.yml` `run:`-block parser (P13-P0-A).

Split out of `tools/entrypoint_mode_check.py` by the <=380-line touched-file
law. It answers one question for the entry-point-mode gate: *which commands does
a workflow execute, and does any of them execute a repository path DIRECTLY
(so that the file's index mode is load-bearing)?*

Line-based and indentation-aware, which is the rule YAML uses for block
scalars: `run: cmd` inline, `run: |` / `run: >-` blocks, `${{ … }}` masked so a
`|` or `;` inside a workflow expression cannot be read as shell syntax, quotes
respected so `"a;b"` is one token, and the documented exemption — `bash`/
`python3`/`node <path>` — recognised by interpreter, not by guesswork.

Stdlib only.
"""
from __future__ import annotations

import re

# The interpreter set. Naming them explicitly is the point: this is the
# documented exemption, so it can be reviewed rather than assumed.
INTERPRETERS = {
    "bash", "sh", "dash", "zsh", "ksh", "python", "python3", "python3.11",
    "python3.12", "python3.13", "node", "nodejs", "perl", "ruby", "pwsh",
    "powershell", "deno", "bun", "awk", "sed",
}
# Leading words that are not the executable: skip them (and, for `timeout`,
# its duration argument) before deciding what a command actually runs.
PREAMBLE = {"env", "command", "time", "sudo", "nohup", "exec", "builtin", "nice"}
SHELL_KEYWORDS = {
    "if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done",
    "case", "esac", "in", "function", "return", "exit", "local", "export",
    "set", "unset", "test", "[", "]", "true", "false", "echo", "printf", "cd",
    "mkdir", "rm", "cp", "mv", "ln", "touch", "chmod", "cat", "tee", "grep",
    "sed", "awk", "find", "xargs", "sort", "head", "tail", "wc", "cut", "tr",
    "jq", "git", "gh", "curl", "wget", "make", "cmake", "ninja", "gcc", "g++",
    "clang", "pip", "pip3", "apt-get", "sudo", "date", "sleep", "read", "shift",
}
PATH_RE = re.compile(r"^(?:\./)?[A-Za-z0-9_.@+-]+(?:/[A-Za-z0-9_.@+-]+)*$")

RUN_RE = re.compile(r"^(\s*)(?:-\s+)?run:(\s*)(.*)$")


# --------------------------------------------------------------------- parsing

def _mask_expressions(text: str) -> str:
    """Blank out `${{ ... }}` spans so `|`, `;` and `}` inside them cannot be
    mistaken for shell syntax. Same length, so line/column maths survives."""
    out, i = list(text), 0
    while i < len(text) - 2:
        if text.startswith("${{", i):
            end = text.find("}}", i + 3)
            end = len(text) if end < 0 else end + 2
            for j in range(i, end):
                if out[j] != "\n":
                    out[j] = " "
            i = end
        else:
            i += 1
    return "".join(out)


def extract_run_blocks(text: str) -> list[tuple[int, str]]:
    """[(line number of the `run:` key, block body)] for every `run:` in a
    workflow file. Handles inline (`run: cmd`) and block scalars (`run: |`,
    `run: >-`), by indentation — the same rule YAML uses."""
    lines = text.splitlines()
    blocks: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        m = RUN_RE.match(lines[i])
        if not m:
            i += 1
            continue
        key_col = len(m.group(1))
        rest = m.group(3)
        if rest[:1] in ("|", ">"):
            body: list[str] = []
            j = i + 1
            while j < len(lines):
                ln = lines[j]
                if ln.strip() and (len(ln) - len(ln.lstrip())) <= key_col:
                    break
                body.append(ln)
                j += 1
            indents = [len(x) - len(x.lstrip()) for x in body if x.strip()]
            cut = min(indents) if indents else 0
            blocks.append((i + 1, "\n".join(x[cut:] for x in body)))
            i = j
        else:
            blocks.append((i + 1, rest))
            i += 1
    return blocks


def split_commands(block: str) -> list[str]:
    """Split a run block into simple commands on newlines, `;`, `&&`, `||` and
    `|` — respecting quotes and `${{ }}`."""
    masked = _mask_expressions(block)
    parts: list[str] = []
    cur: list[str] = []
    quote = ""
    i = 0
    while i < len(masked):
        ch = masked[i]
        if quote:
            cur.append(block[i])
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            cur.append(block[i])
            i += 1
            continue
        if ch == "\\" and i + 1 < len(masked):
            cur.append(block[i:i + 2])
            i += 2
            continue
        two = masked[i:i + 2]
        if two in ("&&", "||"):
            parts.append("".join(cur))
            cur, i = [], i + 2
            continue
        if ch in "\n;|&()":
            parts.append("".join(cur))
            cur, i = [], i + 1
            continue
        cur.append(block[i])
        i += 1
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _tokens(cmd: str) -> list[str]:
    try:
        import shlex
        return shlex.split(cmd, comments=False)
    except ValueError:
        return cmd.split()


def classify_command(cmd: str, tracked: set[str]) -> tuple[str, str]:
    """('direct'|'interpreted'|'other', repo path or '') for one command."""
    toks = _tokens(cmd)
    i = 0
    while i < len(toks):
        t = toks[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):      # env assignment
            i += 1
            continue
        if t in PREAMBLE:
            i += 1
            continue
        if t == "timeout":                                 # timeout <dur> <cmd>
            i += 2
            continue
        break
    if i >= len(toks):
        return "other", ""
    head = toks[i]
    if head in INTERPRETERS:
        for t in toks[i + 1:]:
            if t.startswith("-"):
                continue                      # interpreter flags (-m, -u, -c …)
            cand = t.lstrip("./") if t.startswith("./") else t
            if cand in tracked:
                return "interpreted", cand
            # A path-looking target that is NOT a tracked repo file (a heredoc
            # delimiter, a bare program name like `pip`) is not an entry point
            # and must not pad the exemption list.
            if PATH_RE.match(t) and t.endswith(
                    (".sh", ".py", ".mjs", ".js", ".rb", ".pl", ".bash")):
                return "interpreted", t
        return "other", ""
    if head in SHELL_KEYWORDS or not PATH_RE.match(head):
        return "other", ""
    cand = head.lstrip("./") if head.startswith("./") else head
    if cand in tracked or head.startswith("./"):
        return "direct", cand
    return "other", ""
