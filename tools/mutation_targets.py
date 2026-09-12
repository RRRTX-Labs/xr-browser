#!/usr/bin/env python3
"""tools/mutation_targets.py — the per-core SUITE_MAPS data (P10-T0-c/T1;
split from tools/mutation_test.py for the 400-LOC law). TU -> test
suites that exercise it; the wall-clock fuzz suites stay OUT of the
per-mutant maps (their invariants are covered by the unit suites + the
600 s evidence campaigns)."""
from __future__ import annotations

SUITE_MAPS = {
    # P11-T0-b: the shared primitives are their own mutation core — the KAT
    # pins sha256 (10 vectors incl. the 2^29-bit length case), the moved
    # parser corpus pins json/json_parse (66 checks).
    "common": {
        "sha256.cc": ["test_sha256_kat"],
        "json.cc": ["test_json"],
        "json_parse.cc": ["test_json"],
    },
    "policy": {  # P6 lane — unchanged, byte-for-byte the default path
        "effective_policy.cc": ["test_vectors", "test_resolve", "test_snapshot"],
        "resolve.cc": ["test_vectors", "test_resolve"],
        "resolve_io.cc": ["test_vectors", "test_resolve"],
        "cache.cc": ["test_cache"],
        "snapshot.cc": ["test_snapshot"],
        "store.cc": ["test_store", "test_service"],
        "events.cc": ["test_events"],
        "service.cc": ["test_service"],
    },
    "settings": {
        "settings_schema.cc": ["test_settings_schema"],
        "search.cc": ["test_settings_search", "test_recall_corpus"],
        "sections.cc": ["test_sections"],
        "router.cc": ["test_router"],
        "counters.cc": ["test_counters"],
    },
    "themes": {
        "theme.cc": ["test_theme"],
        "contrast.cc": ["test_contrast", "test_loader"],
        "loader.cc": ["test_loader", "test_host"],
    },
    # P10-T0-c: the commands core joins the matrix (it was the fourth core
    # with no mutation lane — the T0-c debt). Suites follow the same
    # superset-per-TU discipline; the dial test stays out of per-mutant maps
    # except policy_state.cc, which is what it exercises end-to-end.
    "commands": {
        "descriptor.cc": ["test_descriptor", "test_registry"],
        "registry.cc": ["test_registry"],
        "matcher.cc": ["test_matcher"],
        "availability.cc": ["test_availability"],
        "dispatch.cc": ["test_dispatch", "test_host"],
        "shortcuts.cc": ["test_shortcuts"],
        "policy_state.cc": ["test_dial"],
    },
    # P10-T1: the update verifier core joins the matrix (hard gate >=95%).
    # The wall-clock fuzz suite stays out (its invariants are covered by the
    # unit suites + the 600 s evidence campaign); the golden-vector suite IS
    # in the maps — it drives the host binary end-to-end, which is exactly
    # what a verifier mutation must not survive. apply_and_build() builds
    # build/update_host whenever a host-driving suite is mapped.
    "update": {
        "manifest.cc": ["test_manifest_strict", "test_golden_vectors"],
        "verify_policy.cc": ["test_verify_policy", "test_monotonic_downgrade",
                             "test_golden_vectors"],
        "epoch.cc": ["test_verify_policy", "test_update_host",
                     "test_golden_vectors"],
        "cohort.cc": ["test_cohort", "test_golden_vectors"],
        "backoff.cc": ["test_backoff", "test_golden_vectors"],
        "seen.cc": ["test_replay", "test_update_host", "test_golden_vectors"],
    },
    # P11-T4 (T2-era debt, research-log-P11.md D6): the shield core joins
    # the matrix. The golden-vector suite drives the COMPILED host
    # end-to-end (229 cases over all 12 methods incl. the T4 exception
    # surface) — a core mutation must not survive it; per-TU unit suites
    # map as supersets. The wall-clock differential fuzz stays OUT of the
    # per-mutant maps (house rule: unit budgets + the seeded campaigns).
    "shield": {
        "context.cc": ["test_context", "test_match", "test_golden_vectors"],
        "posture.cc": ["test_posture", "test_match", "test_golden_vectors"],
        "bundle.cc": ["test_bundle_strict", "test_apply", "test_match",
                      "test_shield_host", "test_golden_vectors"],
        "scope.cc": ["test_scope", "test_match", "test_golden_vectors"],
        "apply.cc": ["test_apply", "test_golden_vectors"],
        "events.cc": ["test_events", "test_golden_vectors"],
        "match.cc": ["test_match", "test_golden_vectors"],
        "fake_engine.cc": ["test_match", "test_golden_vectors"],
    },
}
