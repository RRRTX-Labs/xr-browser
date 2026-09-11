#!/usr/bin/env python3
"""tools/mutation_targets.py — the per-core SUITE_MAPS data (P10-T0-c/T1;
split from tools/mutation_test.py for the 400-LOC law). TU -> test
suites that exercise it; the wall-clock fuzz suites stay OUT of the
per-mutant maps (their invariants are covered by the unit suites + the
600 s evidence campaigns)."""
from __future__ import annotations

SUITE_MAPS = {
    "policy": {  # P6 lane — unchanged, byte-for-byte the default path
        "json.cc": ["test_vectors", "test_resolve", "test_json"],
        "json_parse.cc": ["test_vectors", "test_resolve", "test_json"],
        "sha256.cc": ["test_vectors"],
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
        "json.cc": ["test_settings_schema", "test_settings_search"],
        "json_parse.cc": ["test_settings_schema", "test_settings_search"],
        "sha256.cc": ["test_counters"],
    },
    "themes": {
        "theme.cc": ["test_theme"],
        "contrast.cc": ["test_contrast", "test_loader"],
        "loader.cc": ["test_loader", "test_host"],
        "json.cc": ["test_theme", "test_loader"],
        "json_parse.cc": ["test_theme", "test_loader"],
        "sha256.cc": ["test_loader"],
    },
    # P10-T0-c: the commands core joins the matrix (it was the fourth core
    # with no mutation lane — the T0-c debt). Suites follow the same
    # superset-per-TU discipline; the dial test stays out of per-mutant maps
    # except policy_state.cc, which is what it exercises end-to-end.
    "commands": {
        "json.cc": ["test_registry", "test_dispatch", "test_shortcuts"],
        "json_parse.cc": ["test_registry", "test_dispatch", "test_shortcuts"],
        "sha256.cc": ["test_descriptor"],
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
        "json.cc": ["test_manifest_strict", "test_verify_policy",
                    "test_golden_vectors"],
        "json_parse.cc": ["test_manifest_strict", "test_verify_policy",
                          "test_golden_vectors"],
        "sha256.cc": ["test_manifest_strict", "test_golden_vectors"],
        "manifest.cc": ["test_manifest_strict", "test_golden_vectors"],
        "verify_policy.cc": ["test_verify_policy", "test_monotonic_downgrade",
                             "test_golden_vectors"],
        "epoch.cc": ["test_verify_policy", "test_update_host",
                     "test_golden_vectors"],
        "cohort.cc": ["test_cohort", "test_golden_vectors"],
        "backoff.cc": ["test_backoff", "test_golden_vectors"],
        "seen.cc": ["test_replay", "test_update_host", "test_golden_vectors"],
    },
}
