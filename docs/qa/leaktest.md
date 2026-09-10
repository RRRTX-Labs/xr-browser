# xr-leaktest (P9-T3) — privilege model and what each lane proves

Owner tool: `tools/leaktest.py` · Result schema:
`docs/contracts/leaktest-result-v1.md` (post-freeze registry).

## The two lanes and their privilege needs (research #6)

| Lane | Privilege needed | Present here? | What it proves |
|---|---|---|---|
| `loopback` | none (binds 127.0.0.1 only) | **yes — real** | the harness's *detection logic* end-to-end: a probe subprocess talks to the userspace tap over a real socket, the tap records targets, the comparator flags anything outside the documented set. |
| `capture` | `tcpdump`/`libpcap` + `CAP_NET_RAW` (or root) | **no** | the OS-level truth of the *whole process tree's* sockets — the lane the endpoint audit (§11.8) runs for real on the farm. |

`loopback` proves the harness can see a leak. `capture` proves there is no
leak to see. Neither substitutes for the other, and the runner never reports
one as the other (`--mode capture` SKIPs visibly when tcpdump is absent).

## Self-verification (mandatory, the point of the harness)

```bash
python3 tools/leaktest.py --self-test
# PASS: leaktest self-test (clean baseline; planted egress detected; blind harness refused)
```

1. clean baseline ⇒ `CLEAN` (no false positive);
2. planted egress (`canary.example.invalid`) ⇒ `LEAK` (no false negative);
3. a *blind* harness (detection suppressed) is reproduced, and check 2 turns
   exactly that state into a non-zero exit — a harness that cannot see a
   leak must fail its own self-test.

## What the loopback lane does NOT prove

It does not observe real browser traffic (there is no browser here), and it
does not prove the product never contacts a host — it proves the *comparator*
and the *planted-egress canary* work. The "zero contacts in a real profile"
proof is the farm capture lane's job, per the endpoint-audit matrix rows:
fresh profile / after import / after each S0 toggle flip (§11.8).

## Farm runbook (capture lane)

```bash
# On the farm runner (root/CAP_NET_RAW), for each policy state:
tcpdump -i any -w /tmp/xr.pcap 'not host <build-host>' &
./xr --fresh-profile …   # or: after-import / after-toggle
kill %1
tshark -r /tmp/xr.pcap -T fields -e ip.dst | sort -u > observed.txt
python3 tools/leaktest.py run --mode capture --observed observed.txt
```

`docs/net-audit.md` (P2) is the prior art: the declared-vs-observed equality
discipline started there for the *build*; this harness extends it to the
*runtime* surface. It extends, it does not duplicate.
